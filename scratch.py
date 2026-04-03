from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from rich.panel import Panel
from rich.markdown import Markdown

class ChatApp(App):
    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", VerticalScroll)
        log.mount(Static(Panel(Markdown("**Agent Zero:** Hello!"), style="cyan")), id="msg_1")
        
        # update later
        def update():
            # query by something custom or by class
            for w in log.query("Static"):
                w.update(Panel(Markdown("**Agent Zero:** Hello! Updated!"), style="cyan"))
        
        self.set_timer(1, update)

if __name__ == "__main__":
    ChatApp().run()
