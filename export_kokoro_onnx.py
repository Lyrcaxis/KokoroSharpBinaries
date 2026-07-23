"""Exports the two Kokoro checkpoints to ONNX with the signature KokoroSharp expects: (tokens[1,T] int64, style[1,256] f32, speed[1] f32) -> audio[N] f32.
Also emits half-size fp16 variants, and speaks a sample line with each exported model (onnx/*.wav) so the results can be heard.

Expects a clone of https://github.com/hexgrad/kokoro next to this script (or inside models_notpushed/).
Checkpoints and voices are read from models_notpushed/ when present, and downloaded from HuggingFace otherwise (e.g. on CI).
"""
import importlib, os, sys, types, wave
import numpy as np, torch, onnx, onnxruntime as ort
from onnx import TensorProto
from onnxconverter_common import float16
from huggingface_hub import hf_hub_download

root = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(root, 'onnx')
os.makedirs(out_dir, exist_ok=True)

# The two Kokoro releases we export, each with a sample voice + phonemes to speak during the test inference
models = [
    ('kokoro',    'hexgrad/Kokoro-82M',         'af_heart', "ðə skˈaɪ əbˈʌv ðə pˈɔɹt wˌʌz ðə kˈʌlɚ ʌv tˈɛləvˌɪʒən, tˈund tʊ ə dˈɛd ʧˈænəl."),
    ('kokoro-zh', 'hexgrad/Kokoro-82M-v1.1-zh', 'zf_001',   "ㄋㄧ3ㄏㄠ3, ㄕㄭ4ㄐㄧㄝ4! ㄏㄨㄢ1ㄧㄥ2ㄕㄭ3ㄩㄥ4."),
]

# Register the kokoro package manually before importing, so kokoro/__init__.py (and its misaki import) never runs
kokoro_src = next(p for p in [f'{root}/models_notpushed/kokoro', f'{root}/kokoro'] if os.path.exists(p))
sys.modules['kokoro'] = types.ModuleType('kokoro')
sys.modules['kokoro'].__path__ = [os.path.join(kokoro_src, 'kokoro')]
from loguru import logger; logger.remove()
KModel = importlib.import_module('kokoro.model').KModel

# Kokoro's forward_with_tokens returns (audio, durations) -- the ONNX-facing model just needs the audio
class KokoroONNX(torch.nn.Module):
    def __init__(self, kmodel): super().__init__(); self.kmodel = kmodel
    def forward(self, tokens, style, speed): return self.kmodel.forward_with_tokens(tokens, style, speed)[0]

for name, repo, voice, phonemes in models:
    # Load the checkpoint, and bake its weight_norms into plain weights so the exported graph is lean and quantizable
    local_dir = os.path.join(root, 'models_notpushed', repo.split('/')[-1])
    has_local = os.path.isdir(local_dir)
    kmodel = KModel(repo_id=repo, config=f'{local_dir}/config.json' if has_local else None, model=f'{local_dir}/{KModel.MODEL_NAMES[repo]}' if has_local else None, disable_complex=True).eval()
    for module in kmodel.modules():
        if torch.nn.utils.parametrize.is_parametrized(module): torch.nn.utils.parametrize.remove_parametrizations(module, 'weight')

    # Tokenize the sample phonemes with the model's own vocab, and grab the matching style vector off the voice
    voice_path = f'{local_dir}/voices/{voice}.pt' if has_local else hf_hub_download(repo_id=repo, filename=f'voices/{voice}.pt')
    ids = [kmodel.vocab[p] for p in phonemes if p in kmodel.vocab]
    tokens = torch.LongTensor([[0, *ids, 0]])
    style = torch.load(voice_path, map_location='cpu', weights_only=False)[len(ids) - 1]
    speed = torch.FloatTensor([1.0])

    # Export (opset 20, dynamic sequence length), then emit an int8-quantized variant alongside
    onnx_path = os.path.join(out_dir, f'{name}.onnx')
    with torch.no_grad():
        torch.onnx.export(
            KokoroONNX(kmodel).eval(), (tokens, style, speed), onnx_path,
            input_names=['tokens', 'style', 'speed'], output_names=['audio'],
            dynamic_axes={ 'tokens': {1: 'sequence_length'}, 'audio': {0: 'audio_length'} },
            opset_version=20, do_constant_folding=True, dynamo=False,
        )
    onnx.checker.check_model(onnx.load(onnx_path))

    # Convert to fp16 to get a half-size variant. Two things the converter would silently get wrong on its own:
    # .. the sine-phase generator (m_source) accumulates phase into the hundreds of radians, where fp16 steps are ~0.5 rad (hello NaNs),
    # .. so that subgraph stays a fp32 island -- and the clamp must be fp16's actual max, as the 1e4 default squashes the 24000.0 sample-rate constant.
    fp32_graph = onnx.load(onnx_path)
    m_source = { node.name for node in fp32_graph.graph.node if '/m_source/' in node.name }
    fp16_graph = float16.convert_float_to_float16(fp32_graph, keep_io_types=True, max_finite_val=65504.0, node_block_list=list(m_source))

    # The converter retypes every edge to fp16 but forgets to update the "to"/"dtype" attributes of pre-existing Cast/Random nodes,
    # .. leaving the graph invalid. We flip those to fp16 ourselves, skipping the boundary casts the converter inserted and the island's insides.
    for node in fp16_graph.graph.node:
        untouchable = node.name in m_source or any(tag in node.name for tag in ['input_cast', 'output_cast', 'cast_to'])
        for attr in node.attribute:
            if node.op_type == 'Cast' and not untouchable and attr.name == 'to' and attr.i == TensorProto.FLOAT: attr.i = TensorProto.FLOAT16
            if 'Random' in node.op_type and not untouchable and attr.name == 'dtype' and attr.i == TensorProto.FLOAT and not any('output_cast' in o for o in node.output): attr.i = TensorProto.FLOAT16

    # Blocked nodes also get ALL their edges wrapped in fp32->fp16->fp32 cast pairs -- even edges between two blocked nodes,
    # .. which would squash the very phase precision we kept the island for. So island-internal edges get rewired to bypass the round-trip.
    island_exits = { node.output[0]: node.input[0] for node in fp16_graph.graph.node if node.op_type == 'Cast' and '_output_cast' in node.name and node.name.rsplit('_output_cast', 1)[0] in m_source }
    for node in fp16_graph.graph.node:
        if node.op_type != 'Cast' or '_input_cast' not in node.name or node.name.rsplit('_input_cast', 1)[0] not in m_source: continue
        if node.input[0] in island_exits: node.input[0] = island_exits[node.input[0]]
    onnx.save(fp16_graph, onnx_path.replace('.onnx', '-fp16.onnx'))

    # Speak the sample line with both exports, so anyone can hear whether they survived the conversion
    for file in [onnx_path, onnx_path.replace('.onnx', '-fp16.onnx')]:
        session = ort.InferenceSession(file, providers=['CPUExecutionProvider'])
        audio = session.run(None, { 'tokens': tokens.numpy(), 'style': style.numpy(), 'speed': speed.numpy() })[0]
        print(f"{os.path.basename(file)}: {audio.shape[0] / 24000:.2f}s of audio, rms {np.sqrt(np.mean(audio ** 2)):.4f}", flush=True)
        
        with wave.open(file.replace('.onnx', '.wav'), 'wb') as f:
            f.setnchannels(1), f.setsampwidth(2), f.setframerate(24000)
            f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
