def sort_numbers(numbers):
    return sorted(numbers)

if __name__ == "__main__":
    user_input = input("Enter a list of numbers separated by spaces: ")
    numbers = [int(num) for num in user_input.split()]
    sorted_numbers = sort_numbers(numbers)
    print(f"Sorted list: {sorted_numbers}")