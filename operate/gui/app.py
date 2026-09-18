"""
GUI Controller Application for Self-Operating Computer
Coordinates StudioWindow, FloatingOverlay, and the background execution thread.
"""
import os
import threading
import queue
from operate.operate import main as operate_main
from operate.gui.studio import StudioWindow
from operate.gui.overlay import FloatingOverlay
from operate.gui.animate import AnimationLoop, lerp, ease_out_expo


def _preload_models():
    """Warm up ML model caches in the background (Phase 5C).

    EasyOCR costs 1.5-4s to instantiate; loading it once here means the first
    OCR click does not pay that cost. Failures are non-fatal.
    """
    try:
        from operate.models.apis import get_ocr_reader

        get_ocr_reader()
    except Exception:
        pass


class GUIApp:
    def __init__(self):
        self.studio = StudioWindow(
            on_start=self.start_execution,
            on_stop=self.stop_execution,
        )
        self.overlay = None
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.event_queue = queue.Queue()

        # Poll the queue from the Tkinter main thread
        self.studio.after(100, self._process_events)

        # Warm up ML caches (EasyOCR/YOLO) off the main thread so the first
        # step is not delayed by multi-second model loads.
        threading.Thread(target=_preload_models, daemon=True).start()

    def start_execution(self, prompt, model, max_steps, use_overlay):
        self.stop_event.clear()

        if use_overlay:
            # Fade out studio before minimizing
            def _fade_and_iconify(t):
                try:
                    self.studio.attributes('-alpha', lerp(1.0, 0.0, t))
                except Exception:
                    pass

            def _do_iconify():
                self.studio.iconify()
                try:
                    self.studio.attributes('-alpha', 1.0)
                except Exception:
                    pass

            AnimationLoop(
                self.studio, 200, _fade_and_iconify,
                easing=ease_out_expo, on_complete=_do_iconify
            ).start()

            # Create floating mini bar (it slides in on its own)
            self.overlay = FloatingOverlay(
                self.studio,
                on_stop=self.stop_execution,
                on_expand=self.restore_studio,
            )

        # Launch background worker
        self.worker_thread = threading.Thread(
            target=self._run_operate_thread,
            args=(model, prompt, max_steps),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_operate_thread(self, model, prompt, max_steps):
        try:
            operate_main(
                model=model,
                terminal_prompt=prompt,
                voice_mode=False,
                verbose_mode=False,
                step_callback=self._on_agent_step,
                stop_event=self.stop_event,
                max_steps=max_steps,
            )
        except Exception as e:
            self.event_queue.put({"type": "error", "error": str(e)})
        finally:
            self.event_queue.put({"type": "finished"})

    def _on_agent_step(self, step_data):
        self.event_queue.put(step_data)

    def stop_execution(self):
        self.stop_event.set()

    def restore_studio(self):
        if self.overlay:
            try:
                if hasattr(self.overlay, 'slide_out_and_destroy'):
                    self.overlay.slide_out_and_destroy()
                else:
                    self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
        self.studio.deiconify()
        self.studio.lift()
        # Fade-in on restore
        try:
            self.studio.attributes('-alpha', 0.0)
            AnimationLoop(
                self.studio, 300,
                lambda t: self.studio.attributes('-alpha', t),
                easing=ease_out_expo,
            ).start()
        except Exception:
            self.studio.attributes('-alpha', 1.0)

    def _process_events(self):
        try:
            while not self.event_queue.empty():
                event = self.event_queue.get_nowait()
                ev_type = event.get("type")

                if ev_type == "status":
                    step = event.get("step")
                    max_steps = event.get("max_steps")
                    msg = event.get("message")
                    screenshot_path = event.get("screenshot_path")

                    if step is not None and max_steps is not None:
                        self.studio.update_progress(step, max_steps, event.get("status", "thinking"))

                    if screenshot_path and os.path.exists(screenshot_path):
                        self.studio.update_screenshot(screenshot_path)
                    elif os.path.exists(os.path.join("screenshots", "screenshot.png")):
                        self.studio.update_screenshot(os.path.join("screenshots", "screenshot.png"))

                    self.studio.log_message(f"[{event.get('status', 'info').upper()}] {msg}", "info")
                    if self.overlay:
                        self.overlay.update_status(
                            event.get("status"), msg, step=step, max_steps=max_steps
                        )

                elif ev_type == "action":
                    op = event.get("operation")
                    detail = event.get("detail")
                    thought = event.get("thought")
                    step = event.get("step")
                    if thought:
                        self.studio.log_message(f"Thought: {thought}", "thought")
                    self.studio.log_message(f"Action: {op} {detail}", "info")
                    if os.path.exists(os.path.join("screenshots", "screenshot.png")):
                        self.studio.update_screenshot(os.path.join("screenshots", "screenshot.png"))
                    if self.overlay:
                        self.overlay.update_status(
                            "acting", f"{op.upper()}: {detail}", step=step
                        )

                elif ev_type == "done":
                    summary = event.get("summary", "Objective complete")
                    self.studio.log_message(f"✓ Complete: {summary}", "success")
                    self.studio.finish_progress("Completed")
                    if self.overlay:
                        self.overlay.update_status("done", summary)

                elif ev_type == "error":
                    err = event.get("error")
                    self.studio.log_message(f"✗ Error: {err}", "error")
                    self.studio.finish_progress("Error")
                    if self.overlay:
                        self.overlay.update_status("error", str(err))

                elif ev_type == "finished":
                    self.studio.on_run_finished()
                    self.studio.finish_progress("Idle")
                    if self.overlay:
                        # Auto-restore studio on finish
                        self.studio.after(1500, self.restore_studio)

        except Exception as e:
            print("Error processing GUI events:", e)

        # Schedule next poll
        self.studio.after(100, self._process_events)

    def run(self):
        self.studio.mainloop()


def launch_gui():
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        os.chdir(project_root)
    except Exception:
        pass
    app = GUIApp()
    app.run()


if __name__ == "__main__":
    launch_gui()
