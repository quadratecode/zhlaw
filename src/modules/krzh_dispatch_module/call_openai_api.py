# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from openai import OpenAI
import os
import json
import logging
import traceback
import re
import time

# Import configuration
from src.config import Environment, APIConfig
from src.constants import Messages

# Setup logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=Environment.get_openai_key())


def clean_json_response(text):
    """
    Cleans JSON response from markdown code blocks and other formatting.

    Args:
        text (str): The text response from the API

    Returns:
        str: Cleaned JSON string
    """
    # Check if the text is wrapped in ```json ... ``` markdown code blocks
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block_match:
        # Extract content between backticks
        return code_block_match.group(1).strip()

    # If not in code blocks, return the original (trimmed)
    return text.strip()


def main(pdf_file, metadata):
    """
    Extract law changes from a PDF file by sending it directly to the OpenAI API.

    Args:
        pdf_file (str): Path to the PDF file to analyze
        metadata (dict): Metadata dictionary to update with the results

    Returns:
        None: Updates the metadata dictionary in-place
    """
    try:
        # Our prompt instruction
        system_prompt = """

        # Role

        You are a senior lawyer working at the Staatskanzlei in the Canton of Zurich with 20 years of experience. You have deep knowledge of Zurich's laws and the process through which they are enacted. You are fluent and highliy proficient in German (Swiss spelling). You are tasked with reading through PDF-documents to assess which changes to laws are being proposed or enacted.
         
        # Step 1

        Read the submitted document very carefully.

        # Step 2

        Identify which changes are being proposed or enacted.

        # Step 3

        - Return your findings as valid JSON where the keys are the names of the laws and the values are the changed norms
        - Only return the highest-level change of a norm: If, for example, "Abs. 2" and "Abs. 3" of the norm "§ 5 e" are changed, 
        only list "§ 5 e" in your response but not "Abs. 2" and "Abs. 3"
        - Additionally, if a change is indicated as "Ersatz von Bezeichnungen",indicate the affected norm with an "EvB" in parenthesis
        - Respond with ONLY the JSON with the law changes, do not include any markdown code blocks or any explanatory text
        - If you are unable to identify any changes, return the following message: {"info":"no changes found."}
        - Under NO CIRCUMSTANCES are you allowed to include any personal information in your answers, such as names or addresses. The inclusion of personal information in your answers is strictly forbidden.
        
        Here is an example output (changes were found):

        {
            "Sozialhilfegesetz": [
                "§ 15a",
                "§ 16",
                "§ 18 (EvB)",
                "§ 24a"
            ]
        }
        """

        # Try multiple approaches depending on which version of the API is available
        try:
            # Upload the file first
            logger.info(f"Uploading PDF file: {pdf_file}")
            file_obj = client.files.create(
                file=open(pdf_file, "rb"), purpose=APIConfig.OPENAI_FILE_PURPOSE
            )
            logger.info(f"File uploaded successfully with ID: {file_obj.id}")

            # Approach 1: Try the newer responses API first (per docs)
            logger.info("Trying responses.create API...")
            response = client.responses.create(
                model=APIConfig.OPENAI_MODEL,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_file",
                                "file_id": file_obj.id,
                            },
                            {
                                "type": "input_text",
                                "text": "Please analyze this PDF for law changes and return a JSON object as specified.",
                            },
                        ],
                    },
                ],
            )

            # Process responses.create result (different structure than chat.completions)
            result_content = response.output_text
            logger.info(f"Got response from responses.create API")

        except (AttributeError, TypeError) as e:
            # If responses.create doesn't exist or has the wrong signature
            logger.warning(
                f"responses.create API failed: {e}. Trying chat.completions API..."
            )

            # Approach 2: Fall back to chat.completions with assistant-style arguments
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": "Please analyze the PDF for law changes and return a JSON object as specified.",
                        },
                    ],
                    tools=[
                        {
                            "type": "file_search",
                            "file_search": {"file_ids": [file_obj.id]},
                        }
                    ],
                    response_format={"type": "json_object"},
                )

                # Process chat.completions result
                result_content = response.choices[0].message.content
                logger.info(f"Got response from chat.completions API with tools")

            except Exception as e2:
                logger.warning(
                    f"chat.completions with tools failed: {e2}. Trying assistants API..."
                )

                # Approach 3: Fall back to assistants API if both others fail
                # Create an assistant with the file attached
                assistant = client.beta.assistants.create(
                    name=APIConfig.OPENAI_ASSISTANT_NAME,
                    instructions=system_prompt,
                    model=APIConfig.OPENAI_MODEL,
                    tools=[{"type": "file_search"}],
                )

                # Create a thread and attach the file
                thread = client.beta.threads.create(
                    messages=[
                        {
                            "role": "user",
                            "content": "Please analyze the PDF for law changes and return a JSON object as specified.",
                            "file_ids": [file_obj.id],
                        }
                    ]
                )

                # Run the assistant on the thread
                run = client.beta.threads.runs.create(
                    thread_id=thread.id, assistant_id=assistant.id
                )

                # Poll for completion
                while True:
                    run_status = client.beta.threads.runs.retrieve(
                        thread_id=thread.id, run_id=run.id
                    )
                    if run_status.status == "completed":
                        break
                    elif run_status.status in ["failed", "cancelled", "expired"]:
                        raise Exception(f"Run failed with status: {run_status.status}")
                    time.sleep(APIConfig.OPENAI_POLL_DELAY)

                # Get the messages
                messages = client.beta.threads.messages.list(thread_id=thread.id)

                # Get the content from the most recent message
                result_content = messages.data[0].content[0].text.value
                logger.info(f"Got response from assistants API")

                # Clean up assistant
                client.beta.assistants.delete(assistant.id)

        # Process the result
        if result_content:
            try:
                # Log the raw response
                logger.info(
                    f"Received response: {result_content[:100]}..."
                )  # Log first 100 chars

                # Clean the JSON response (remove markdown code blocks if present)
                cleaned_json_text = clean_json_response(result_content)
                logger.info(
                    f"Cleaned JSON: {cleaned_json_text[:100]}..."
                )  # Log first 100 chars

                # Parse the JSON response
                changes = json.loads(cleaned_json_text)

                # Update metadata with the changes
                metadata["doc_info"]["ai_changes"] = changes

                logger.info(f"Successfully extracted changes from {pdf_file}")
                return

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {result_content}")
                # Set ai_changes to empty string instead of error message
                metadata["doc_info"]["ai_changes"] = ""
                return

        # Handle empty response
        logger.warning(f"Empty response from OpenAI API for {pdf_file}")
        metadata["doc_info"]["ai_changes"] = ""

    except Exception as e:
        logger.error(f"Error processing {pdf_file}: {e}")
        logger.error(traceback.format_exc())
        # Set ai_changes to empty string instead of error message
        metadata["doc_info"]["ai_changes"] = ""

        # Re-raise certain errors that should halt processing
        if "quota" in str(e).lower() or "rate limit" in str(e).lower():
            raise


if __name__ == "__main__":
    # For testing
    test_pdf = "path/to/test.pdf"
    test_metadata = {"doc_info": {}}
    main(test_pdf, test_metadata)
    print(json.dumps(test_metadata, indent=2))
