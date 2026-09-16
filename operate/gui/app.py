"""
GUI Controller Application for Self-Operating Computer
Coordinates StudioWindow, FloatingOverlay, and the background execution thread.
"""
import threading
import queue
from operate.operate import main as operate_main
from operate.gui.studio import StudioWindow
from operate.gui.overlay import FloatingOverlay


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

    def start_execution(self, prompt, model, max_steps, use_overlay):
        self.stop_event.clear()

        if use_overlay:
            # Create floating mini bar and iconify/minimize studio
            self.overlay = FloatingOverlay(
                self.studio,
                on_stop=self.stop_execution,
                on_expand=self.restore_studio,
            )
            self.studio.iconify()

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
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
        self.studio.deiconify()
        self.studio.lift()

    def _process_events(self):
        try:
            while not self.event_queue.empty():
                event = self.event_queue.get_nowait()
                ev_type = event.get("type")

                if ev_type == "status":
                    step = event.get("step")
                    max_steps = event.get("max_steps")
                    msg = event.get("message")
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
                    if self.overlay:
                        self.overlay.update_status(
                            "acting", f"{op.upper()}: {detail}", step=step
                        )

                elif ev_type == "done":
                    summary = event.get("summary", "Objective complete")
                    self.studio.log_message(f"✓ Complete: {summary}", "success")
                    if self.overlay:
                        self.overlay.update_status("done", summary)

                elif ev_type == "error":
                    err = event.get("error")
                    self.studio.log_message(f"✗ Error: {err}", "error")
                    if self.overlay:
                        self.overlay.update_status("error", str(err))

                elif ev_type == "finished":
                    self.studio.on_run_finished()
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
