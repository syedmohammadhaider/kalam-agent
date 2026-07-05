import os

def print_tree(path, prefix=''):
    if not os.path.exists(path):
        print(f"{prefix}No such file or directory: '{path}'")
        return

    if os.path.isfile(path):
        print(f"{prefix}{os.path.basename(path)}")
        return

    print(f"{prefix}{os.path.basename(path)}/")
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            print_tree(item_path, prefix + '    ')
        else:
            print_tree(item_path, prefix + '    ')

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python filetree.py <directory>")
        sys.exit(1)
    print_tree(sys.argv[1])