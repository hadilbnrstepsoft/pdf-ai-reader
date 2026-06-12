def chunk_text(text_list, chunk_size=500):
    chunks = []

    for text in text_list:
        words = text.split()

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            chunks.append(chunk)

    return chunks