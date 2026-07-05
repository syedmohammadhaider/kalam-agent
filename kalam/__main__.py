import argparse

from kalam.app import KalamApp


def main():
    parser = argparse.ArgumentParser(description="Kalam — AI coding agent")
    parser.add_argument("-p", "--path", help="project root path (default: cwd)")
    args = parser.parse_args()
    app = KalamApp(project_path=args.path)
    app.run()


if __name__ == "__main__":
    main()
