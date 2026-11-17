"""Execute every notebook cell in smoke mode, using verified download caches."""
import base64
import io
import json
import os
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import nbformat
import matplotlib

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
notebook = nbformat.read(ROOT / "notebooks/DSS_POI_Colab.ipynb", as_version=4)
nbformat.validate(notebook)
active_outputs = []
capture = io.StringIO()


def flush_capture():
    value = capture.getvalue()
    if value:
        active_outputs.append(nbformat.v4.new_output("stream", name="stdout", text=value))
        capture.seek(0)
        capture.truncate(0)


def display(value):
    flush_capture()
    if hasattr(value, "savefig"):
        buffer = io.BytesIO()
        value.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
        data = {"image/png": base64.b64encode(buffer.getvalue()).decode("ascii"), "text/plain": "Matplotlib figure"}
    elif hasattr(value, "_repr_html_"):
        data = {"text/html": value._repr_html_(), "text/plain": str(value)}
    else:
        data = {"text/plain": str(value)}
    active_outputs.append(nbformat.v4.new_output("display_data", data=data))


context = {"__name__":"__notebook__", "display":display}
execution_count = 0
for index, cell in enumerate(notebook.cells):
    if cell.cell_type != "code":
        continue
    source = "\n".join(line for line in cell.source.splitlines() if not line.startswith("%pip"))
    if 'RUN_MODE = "full"' in source:
        source = source.replace('RUN_MODE = "full"', 'RUN_MODE = "smoke"')
        source = source.replace('Path("dss_colab_v2")', 'Path("outputs/datasets")')
        source = source.replace('OUT = WORK / "artifacts"', 'OUT = Path("outputs/qa/notebook_v3/artifacts")')
    print(f"Executing cell {index}", flush=True)
    active_outputs = []
    with redirect_stdout(capture), redirect_stderr(capture):
        if source.startswith("%%writefile "):
            header, _, body = source.partition("\n")
            arguments = shlex.split(header[len("%%writefile "):].format(WORK=context["WORK"].as_posix()))
            destination = Path(arguments[-1])
            mode = "a" if "-a" in arguments else "w"
            with destination.open(mode, encoding="utf-8", newline="\n") as target:
                target.write(body + "\n")
            print(f"Wrote {destination} ({mode})")
        else:
            exec(compile(source, f"notebook-cell-{index}", "exec"), context)
    flush_capture()
    execution_count += 1
    cell.source = source
    cell.execution_count = execution_count
    cell.outputs = active_outputs
    streams = "".join(output.get("text", "") for output in active_outputs if output.output_type == "stream")
    if streams:
        print(streams[-1500:], flush=True)
for dataset in ("danang", "gowalla"):
    assert (context["OUT"] / dataset / "tas_gnn.pt").is_file()
assert (context["OUT"] / "all_datasets_comparison.csv").is_file()
for filename in ("dataset_quality.json", "split_audit.json", "research_summary.md", "resources.csv", "all_visit_comparison.csv"):
    assert (context["OUT"] / filename).is_file(), filename
for dataset in ("danang", "gowalla"):
    for suffix in ("eda.png", "learning_curves.png", "comparison.png", "error_slices.png", "paired_user_ci.csv"):
        assert (context["OUT"] / f"{dataset}_{suffix}").is_file()
assert context["checked"] == sum(len(report["model_configs"]) for reports in context["reports"].values() for report in reports)
notebook.cells[0].source = (
    "# LOCAL SMOKE QA — technical verification only\n\n"
    "CPU/local dependency environment; 24 users, 1 epoch, 2 seeds; not benchmark results. "
    "The %pip install line was skipped; %%writefile was emulated by the QA runner. "
    "This file records the actual configuration, tables and figures from that smoke run.\n\n" + notebook.cells[0].source)
notebook.metadata["qa"] = {"mode": "local_smoke", "pip_install_skipped": True, "writefile_emulated": True}
destination = ROOT / "outputs/qa/notebook_v3/DSS_POI_Colab.smoke.executed.ipynb"
destination.parent.mkdir(parents=True, exist_ok=True)
nbformat.validate(notebook)
nbformat.write(notebook, destination)
print("Executed smoke notebook:", destination)
print("PASS: schema + every code cell + BOTH data pipelines + 2-seed smoke + ablations + bootstrap + figures + all checkpoint roundtrips + ZIP checksums")
