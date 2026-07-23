import os, shutil, torch, numpy as np
from huggingface_hub import HfApi, hf_hub_download

# The two Kokoro releases whose voices (and docs) we repackage, and the folders they land in
repos = { 'hexgrad/Kokoro-82M': 'voices', 'hexgrad/Kokoro-82M-v1.1-zh': 'voices/voices-zh' }

for repo, folder in repos.items():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)
    os.makedirs(path, exist_ok=True)
    all_files = HfApi().list_repo_files(repo)

    # Get all root .md files (DOCS)
    for file in all_files:
        if '/' in file or not file.endswith('.md'): continue
        print(f"Downloading {repo}/{file}")
        shutil.copyfile(hf_hub_download(repo_id=repo, filename=file), os.path.join(path, file))

    # Get all .pt files (VOICES) and convert them to .npy
    for file in all_files:
        if not file.startswith('voices/') or not file.endswith('.pt'): continue
        print(f"Downloading {repo}/{file}")
        voice_style = torch.load(hf_hub_download(repo_id=repo, filename=file), weights_only = False).numpy().astype(np.float32)
        np.save(os.path.join(path, os.path.basename(file).replace('.pt', '.npy')), voice_style)

    # List all files
    print("---- ST LISTING FILES ----- ")
    for file in sorted(os.listdir(path)): print("-", file)
    print("---- ED LISTING FILES ----- ")
