# a = input("what is your name")
# b = input("how much do you earn")
# if int(b) == 0:
#     raise ZeroDivisionError("b is 0 so stopping the program")
# if a.isnumeric():
#     raise Exception("numbers are not allowed")
c = input("enter your name")
try:
    print(a)
except Exception as e:
    if c == "sparsh":
        print("sparsh is blocked he is not allowed")
    print("exception handled")
