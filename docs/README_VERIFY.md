# Verification

This scaffold has two verification paths.

Use the normal install path when Python, pip, npm, and git are available:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest

cd ..\frontend
npm install
npm run build
```

From the project root, use the offline path when local dependency/cache creation is blocked:

```powershell
$py = "C:\Users\nayak\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$env:PYTHONDONTWRITEBYTECODE = "1"
& $py scripts\verify_backend.py
& $py scripts\verify_frontend_static.py
```

The backend verifier checks syntax, scientist configs, the corpus manifest, local retrieval, memory, context assembly, and the REST chat orchestration path. The frontend verifier checks package scripts, required source files, the chat service, and responsive CSS presence.

The small files under `data/corpus/raw/*` are seed texts for offline verification. Public-domain manifest downloads can replace the Einstein, Newton, Tesla, and Curie seeds when network access is available. The Feynman file remains a curator-approved placeholder until a suitable source is selected.
