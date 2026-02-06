from rich.console import Console

AGENT_NAME = "Seira"

console = Console()

def main():
    console.print(f"[bold green]{AGENT_NAME} online[/bold green]")
    console.print("Type 'exit' to quit.\n")

    while True:
        user_input = input("> ").strip()

        if user_input.lower() in {"exit", "quit"}:
            console.print("[cyan]Shutting down.[/cyan]")
            break

        if not user_input:
            continue

        console.print(f"[cyan]You said:[/cyan] {user_input}")

if __name__ == "__main__":
    main()
