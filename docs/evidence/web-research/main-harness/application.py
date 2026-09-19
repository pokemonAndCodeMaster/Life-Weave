import os
from pathlib import Path
from src.cli import migrate
from src.api.app import create_app
migrate()
app=create_app()
root=Path(os.environ['LIFEWEAVE_ACCEPTANCE_ROOT'])
app.state.root=root
app.state.local_workers.root=root
app.state.task_sources.root=root
app.state.conversations.interpreter.root=root
app.state.research_outputs.root=root
app.state.lifeweave_runtime_service.runtime_root=root/'.runtime/runs'
