from backend.chat import ask_pdf

while True:
    q = input("\nQuestion: ")
    if q == "exit":
        break

    answer = ask_pdf(q)

    print("\n--- ANSWER ---")
    print(answer)