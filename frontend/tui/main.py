import argparse
from app import KalamApp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kalam AI Coding Agent")
    parser.add_argument("-p", "--path", help="Project root path (default: current directory)")
    args = parser.parse_args()

    app = KalamApp(project_path=args.path)
    app.run()
