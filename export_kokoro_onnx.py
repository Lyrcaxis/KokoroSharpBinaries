"""Exports the two Kokoro checkpoints to ONNX with the signature KokoroSharp expects: (tokens[1,T] int64, style[1,256] f32, speed[1] f32) -> audio[N] f32.
Also emits int8-quantized variants, and speaks a sample line with each exported model (onnx/*.wav) so the results can be heard.

Expects a clone of https://github.com/hexgrad/kokoro next to this script (or inside models_notpushed/).
Checkpoints and voices are read from models_notpushed/ when present, and downloaded from HuggingFace otherwise (e.g. on CI).
"""
import importlib, os, sys, types, wave
import numpy as np, torch, onnx, onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
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
    quantize_dynamic(onnx_path, onnx_path.replace('.onnx', '-int8.onnx'), weight_type=QuantType.QUInt8)

    # Speak the sample line with both exports, so anyone can hear whether they survived the conversion
    for file in [onnx_path, onnx_path.replace('.onnx', '-int8.onnx')]:
        session = ort.InferenceSession(file, providers=['CPUExecutionProvider'])
        audio = session.run(None, { 'tokens': tokens.numpy(), 'style': style.numpy(), 'speed': speed.numpy() })[0]
        print(f"{os.path.basename(file)}: {audio.shape[0] / 24000:.2f}s of audio, rms {np.sqrt(np.mean(audio ** 2)):.4f}", flush=True)
        
        with wave.open(file.replace('.onnx', '.wav'), 'wb') as f:
            f.setnchannels(1), f.setsampwidth(2), f.setframerate(24000)
            f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
