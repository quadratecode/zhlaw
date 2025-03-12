# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from openai import OpenAI
import os
import json
import re

OpenAI.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()


def convert_to_valid_json(text):
    # Remove code block markers
    text = text.replace("```json", "").replace("```", "")

    # Remove newline characters
    text = text.replace("\n", "")

    # Replace escaped backslashes with a single backslash
    text = text.replace("\\", "")

    # Return two or more spaces with a single space
    text = " ".join(text.split())

    return text


def create_message_object(file_content, thread_id):

    message_object = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=file_content,
    )

    return message_object



def detect_changes(file_content, metadata):

    # Step 1: Create an Assistant
    my_assistant_object = client.beta.assistants.retrieve(
        "asst_47PympQ8GNAkuwCBbOrrv9z8"
    )
    my_assistant_id = my_assistant_object.id

    # Step 3: Create a Thread
    my_thread_object = client.beta.threads.create()
    my_thread_id = my_thread_object.id

    # Step 4: Add a Message to a Thread
    my_message_object = create_message_object(file_content, my_thread_id)

    # Step 5: Run the Assistant
    my_run = client.beta.threads.runs.create(
        thread_id=my_thread_id,
        assistant_id=my_assistant_id,
    )

    # Step 6: Periodically retrieve the Run to check on its status to see if it has moved to completed
    while my_run.status in ["queued", "in_progress"]:
        keep_retrieving_run = client.beta.threads.runs.retrieve(
            thread_id=my_thread_id, run_id=my_run.id
        )
        print(f"Run status: {keep_retrieving_run.status}")

        if keep_retrieving_run.status == "completed":
            print("\n")

            # Step 6: Retrieve the Messages added by the Assistant to the Thread
            all_messages = client.beta.threads.messages.list(thread_id=my_thread_id)

            print("------------------------------------------------------------ \n")

            print(f"User: {my_message_object.content[0].text.value}")
            print(f"Assistant: {all_messages.data[0].content[0].text.value}")

            # Get answer
            gpt_answer = all_messages.data[0].content[0].text.value
            try:
                # Convert answer to valid json
                gpt_answer = convert_to_valid_json(gpt_answer)
                gpt_answer = json.loads(gpt_answer)
            except:
                pass
            # Add answer to metadata

            metadata["doc_info"]["ai_changes"] = gpt_answer

            break
        elif (
            keep_retrieving_run.status == "queued"
            or keep_retrieving_run.status == "in_progress"
        ):
            pass
        else:
            print(f"Run status: {keep_retrieving_run.status}")
            break


def main(file, metadata):

    file_type = file.split(".")[-1]

    with open(file, "r") as f:
        file_content = f.read()

    # Remove line breaks for html files (keep for csv)
    if file_type == "html":
        # Remove line breaks followed by any number of spaces
        file_content = re.sub(r"\n\s*", "", file_content)

    # Reduce multiple spaces to single space
    file_content = " ".join(file_content.split())

    # Detect changes
    detect_changes(file_content, metadata)


if __name__ == "__main__":
    main()
