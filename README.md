# ComfyUI PNG Workflow Injector

*Inject a ComfyUI workflow JSON into the metadata of a PNG screenshot, so ComfyUI can load the workflow when the image is dragged in.*

---

Using this command, the [inject_comfy_workflow.py](inject_comfy_workflow.py) script writes the ComfyUI workflow JSON (in workflow.json) into the screenshot.png's `workflow` metadata text chunk expected by ComfyUI.

```bash
./inject_comfy_workflow.py screenshot.png workflow.json screenshot_with_workflow_metadata.png
```


