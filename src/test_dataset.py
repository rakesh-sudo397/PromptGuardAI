from datasets import load_dataset

dataset = load_dataset("deepset/prompt-injections")

count = 0

for sample in dataset["train"]:
    if sample["label"] == 1:
        print(sample)
        print("-" * 80)

        count += 1

        if count == 10:
            break