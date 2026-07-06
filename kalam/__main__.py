import argparse

from kalam.app import KalamApp


def main():
    parser = argparse.ArgumentParser(description="Kalam — AI coding agent")
    parser.add_argument("-p", "--path", help="project root path (default: cwd)")
    parser.add_argument("-d", "--debug", action="store_true", help="enable debug logging")
    args = parser.parse_args()
    app = KalamApp(project_path=args.path, debug=args.debug)
    app.run()


if __name__ == "__main__":
    main()
