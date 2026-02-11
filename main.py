from rich.console import Console

AGENT_NAME = "Seira"
console = Console()

def main():
    console.print(f"[bold green]{AGENT_NAME} System Terminal[/bold green]")
    console.print("[yellow]Subject: Ancient One (Origin: 2026 Terra)[/yellow]")
    console.print("Type 'exit' to enter cryosleep standby.\n")

    while True:
        user_input = input("> ").strip()

        if user_input.lower() in {"exit", "quit"}:
            console.print("[cyan]Standby mode engaged. Monitoring pulses...[/cyan]")
            break

        if not user_input:
            continue

        console.print(f"[cyan]Local Input Logged:[/cyan] {user_input}")

if __name__ == "__main__":
    main()