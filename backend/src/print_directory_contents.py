import os

def print_directory_contents(directory_path):
    try:
        for item in os.listdir(directory_path):
            print(item)
    except FileNotFoundError:
        print(f"Directory {directory_path} not found.")