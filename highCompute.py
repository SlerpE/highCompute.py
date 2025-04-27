import gradio as gr
import requests
import json
import os
import re
from dotenv import load_dotenv
import time

load_dotenv()

DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_LLM_MODEL = "local-model"
DEFAULT_API_KEY = None

LOCAL_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT", DEFAULT_ENDPOINT)
LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
LLM_API_KEY = os.getenv("LLM_API_KEY", DEFAULT_API_KEY)

def call_llm(prompt, chat_history_gradio=None, temperature=0.7, top_p=None, top_k=None, stream=False):
    messages = []
    if chat_history_gradio:
        for user_msg, assistant_msg in chat_history_gradio:
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                 messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": prompt})

    payload_dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": stream
    }
    if top_p is not None and top_p < 1.0:
         payload_dict["top_p"] = top_p
    if top_k is not None and top_k > 0:
         payload_dict["top_k"] = top_k

    payload = json.dumps(payload_dict)
    headers = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'text/event-stream' if stream else 'application/json'}

    if LLM_API_KEY:
        headers['Authorization'] = f'Bearer {LLM_API_KEY}'
        print(f"Sending request to {LOCAL_API_ENDPOINT} using API Key.")
    else:
        print(f"Sending request to {LOCAL_API_ENDPOINT} without API Key.")

    print(f"Model: '{LLM_MODEL}', Stream: {stream}, Payload: {payload[:200]}...")

    try:
        response = requests.post(LOCAL_API_ENDPOINT, headers=headers, data=payload.encode('utf-8'), timeout=36000, stream=stream)
        response.raise_for_status()

        if stream:
            print("Processing stream...")
            for chunk_bytes in response.iter_content(chunk_size=None):
                 if not chunk_bytes:
                     continue
                 try:
                     lines = chunk_bytes.decode('utf-8').splitlines()
                     for line in lines:
                         if line.startswith("data:"):
                             line_data = line[len("data:"):].strip()
                             if line_data == "[DONE]":
                                 print("Stream finished.")
                                 break
                             try:
                                 chunk = json.loads(line_data)
                                 if chunk.get("choices") and len(chunk["choices"]) > 0:
                                     delta = chunk["choices"][0].get("delta", {})
                                     content_chunk = delta.get("content")
                                     if content_chunk:
                                         yield content_chunk
                             except json.JSONDecodeError:
                                 print(f"Warning: Could not decode stream line JSON: {line_data}")
                                 continue
                             except Exception as e:
                                 print(f"Error processing stream chunk: {e}, Line: {line_data}")
                                 yield f"\n[Error processing stream chunk: {e}]"
                                 break
                     else:
                         continue
                     break
                 except UnicodeDecodeError:
                     print(f"Warning: Could not decode chunk as UTF-8: {chunk_bytes[:100]}...")
                     continue
            print("Stream processing complete.")

        else:
            response.encoding = response.apparent_encoding if response.encoding is None else response.encoding
            data = response.json()
            print(f"Received non-stream response: {json.dumps(data, ensure_ascii=False, indent=2)}")

            if data.get("choices") and len(data["choices"]) > 0:
                message_content = data["choices"][0].get("message", {}).get("content")
                if message_content:
                    yield message_content.strip()
                else:
                    print("Error: 'content' key not found in LLM response choice.")
                    yield "Error: 'content' not found in LLM response."
            else:
                print("Error: 'choices' array is missing, empty, or invalid in LLM response.")
                yield "Error: Invalid format in LLM response (missing 'choices')."

    except requests.exceptions.Timeout:
        print(f"Network error: Request timed out after 36000 seconds.")
        yield "Network error: Request timed out."
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        yield f"Network error: {e}"
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from server. Response text: {response.text}")
        yield f"Error: Failed to read server response (JSONDecodeError: {e}). Check server logs."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        yield f"An unexpected error occurred: {e}"


def low_compute(user_input, history, temperature, top_p, top_k):
    yield "[Status] Sending request directly to LLM..."
    print("[Low Mode] Sending LLM request (streaming)...")
    full_response = ""
    for chunk in call_llm(user_input, chat_history_gradio=history, temperature=temperature, top_p=top_p, top_k=top_k, stream=True):
        full_response += chunk
        yield full_response
    print("[Low Mode] Response stream finished.")


def medium_compute(user_input, history, temperature, top_p, top_k):
    yield "[Status] Starting task decomposition (1 level)..."
    print("[Medium Mode] Starting task decomposition...")
    control_temp = max(0.1, temperature * 0.5)
    decompose_prompt = f'Original task: "{user_input}". Break it down into logical subtasks needed to solve it (numbered list). Be concise.'

    subtasks_text_gen = call_llm(decompose_prompt, temperature=control_temp, top_p=top_p, top_k=top_k, stream=False)
    subtasks_text = next(subtasks_text_gen, "Error: No response from decomposition.")
    if subtasks_text.startswith("Error:") or subtasks_text.startswith("Network error:"):
        yield "[Status] Decomposition failed. Answering directly..."
        print(f"[Medium Mode] Decomposition failed: {subtasks_text}. Responding directly (streaming)...")
        full_response = ""
        for chunk in call_llm(user_input, chat_history_gradio=history, temperature=temperature, top_p=top_p, top_k=top_k, stream=True):
            full_response += chunk
            yield full_response
        print("[Medium Mode] Direct response stream finished after decomposition failure.")
        return

    subtasks = re.findall(r"^\s*\d+\.\s*(.*)", subtasks_text, re.MULTILINE)

    if not subtasks:
        yield "[Status] Decomposition returned no subtasks. Answering directly..."
        print("[Medium Mode] Decomposition returned no numbered points. Responding directly (streaming)...")
        full_response = ""
        for chunk in call_llm(user_input, chat_history_gradio=history, temperature=temperature, top_p=top_p, top_k=top_k, stream=True):
            full_response += chunk
            yield full_response
        print("[Medium Mode] Direct response stream finished after no subtasks found.")
        return

    yield f"[Status] Task divided into {len(subtasks)} subtasks. Solving them one by one..."
    print(f"[Medium Mode] Task divided into {len(subtasks)} subtasks.")
    subtask_results = []
    temp_history_medium = history.copy() if history else []

    for i, subtask in enumerate(subtasks):
        subtask = subtask.strip()
        if not subtask: continue
        yield f"[Status] Solving subtask {i+1}/{len(subtasks)}: \"{subtask}...\""
        print(f"[Medium Mode] Solving subtask {i+1}/{len(subtasks)}: \"{subtask}\"...")
        solve_prompt = f'Original overall task: "{user_input}". Current subtask: "{subtask}". Provide a detailed solution or answer for this specific subtask.'

        subtask_result_gen = call_llm(solve_prompt, chat_history_gradio=temp_history_medium, temperature=temperature, top_p=top_p, top_k=top_k, stream=False)
        subtask_result = next(subtask_result_gen, f"Error: No response for subtask {i+1}.")
        subtask_results.append({"subtask": subtask, "result": subtask_result})
        print(f"[Medium Mode] Subtask {i+1} result: Received.")
        if subtask_result.startswith("Error:") or subtask_result.startswith("Network error:"):
             yield f"[Status] Error solving subtask {i+1}. Aborting and attempting direct answer..."
             print(f"[Medium Mode] Error solving subtask {i+1}: {subtask_result}. Responding directly (streaming)...")
             full_response = ""
             for chunk in call_llm(user_input, chat_history_gradio=history, temperature=temperature, top_p=top_p, top_k=top_k, stream=True):
                 full_response += chunk
                 yield full_response
             print("[Medium Mode] Direct response stream finished after subtask error.")
             return

    yield "[Status] All subtasks solved. Synthesizing final response..."
    print("[Medium Mode] Synthesizing final response (streaming)...")
    synthesis_prompt = f'Original task: "{user_input}". The task was broken down and the results for each subtask are:\n---\n'
    for i, res in enumerate(subtask_results):
        synthesis_prompt += f"{i+1}. Subtask: {res['subtask']}\n   Result: {res['result']}\n---\n"
    synthesis_prompt += "Combine these results into a single, coherent, well-formatted final response that directly addresses the original task. Do not just list the subtasks and results; synthesize them."

    full_response = ""
    for chunk in call_llm(synthesis_prompt, temperature=control_temp, top_p=top_p, top_k=top_k, stream=True):
        full_response += chunk
        yield full_response
    print("[Medium Mode] Final response stream synthesized.")


def high_compute(user_input, history, temperature, top_p, top_k):
    yield "[Status] Starting task decomposition (Level 1)..."
    print("[High Mode] Starting task decomposition (Level 1)...")
    control_temp = max(0.1, temperature * 0.5)
    decompose_prompt_l1 = f'Original complex task: "{user_input}". Break this down into major high-level stages or components (Level 1 - numbered list). Keep items distinct and logical.'

    subtasks_l1_text_gen = call_llm(decompose_prompt_l1, temperature=control_temp, top_p=top_p, top_k=top_k, stream=False)
    subtasks_l1_text = next(subtasks_l1_text_gen, "Error: No response from L1 decomposition.")

    if subtasks_l1_text.startswith("Error:") or subtasks_l1_text.startswith("Network error:"):
        yield "[Status] Level 1 decomposition failed. Falling back to Medium compute mode..."
        print(f"[High Mode] Decomposition failed (Level 1): {subtasks_l1_text}. Falling back to Medium Mode...")
        yield from medium_compute(user_input, history, temperature, top_p, top_k)
        return

    subtasks_l1 = re.findall(r"^\s*\d+\.\s*(.*)", subtasks_l1_text, re.MULTILINE)

    if not subtasks_l1:
        yield "[Status] Level 1 decomposition returned no subtasks. Falling back to Medium compute mode..."
        print("[High Mode] Decomposition returned no subtasks (Level 1). Falling back to Medium Mode...")
        yield from medium_compute(user_input, history, temperature, top_p, top_k)
        return

    yield f"[Status] Task divided into {len(subtasks_l1)} Level 1 stages. Processing stages..."
    print(f"[High Mode] Task divided into {len(subtasks_l1)} Level 1 subtasks.")
    subtasks_l1_results = []
    temp_history_high = history.copy() if history else []

    for i, subtask_l1 in enumerate(subtasks_l1):
        subtask_l1 = subtask_l1.strip()
        if not subtask_l1: continue
        yield f"[Status] Processing Level 1 stage {i+1}/{len(subtasks_l1)}: \"{subtask_l1}...\". Starting mandatory Level 2 decomposition..."
        print(f"[High Mode] Working on Level 1 subtask ({i+1}/{len(subtasks_l1)}): \"{subtask_l1}\"")
        print(f"[High Mode]   Attempting MANDATORY Level 2 decomposition for: \"{subtask_l1}\"...")

        decompose_prompt_l2 = f'Current high-level stage (Level 1): "{subtask_l1}". Break THIS stage down into smaller, actionable steps (Level 2 - numbered list). You MUST provide the steps as a numbered list starting with "1.". Even if there is only one step, write "1. {subtask_l1}". Do not use phrases like "No further decomposition needed". Just provide the list.'

        subtasks_l2_text_gen = call_llm(decompose_prompt_l2, temperature=control_temp, top_p=top_p, top_k=top_k, stream=False)
        subtasks_l2_text = next(subtasks_l2_text_gen, f"Error: No response for L2 decomposition of stage {i+1}.")
        print(f"[DEBUG High Mode] Raw L2 decomposition text for '{subtask_l1}':\n>>>\n{subtasks_l2_text}\n<<<")

        if subtasks_l2_text.startswith("Error:") or subtasks_l2_text.startswith("Network error:"):
            yield f"[Status] Stage {i+1}: L2 decomposition failed ({subtasks_l2_text}). Forcing L1 task as single L2 step."
            print(f"[High Mode]   L2 decomposition failed for \"{subtask_l1}\": {subtasks_l2_text}. Forcing it as a single L2 step.")
            subtasks_l2 = [subtask_l1.strip()]
        else:
            subtasks_l2 = re.findall(r"^\s*\d+\.\s*(.*)", subtasks_l2_text, re.MULTILINE)
            if not subtasks_l2:
                yield f"[Status] Stage {i+1}: L2 decomposition format issue or LLM refusal. Forcing L1 task as single L2 step."
                print(f"[High Mode]   L2 decomposition failed/refused for \"{subtask_l1}\". Forcing it as a single L2 step.")
                subtasks_l2 = [subtask_l1.strip()]


        yield f"[Status] Stage {i+1} processing {len(subtasks_l2)} Level 2 step(s)..."
        print(f"[High Mode]   Processing {len(subtasks_l2)} Level 2 step(s) for L1 subtask \"{subtask_l1}\".")
        subtasks_l2_results = []
        abort_stage = False
        for j, subtask_l2 in enumerate(subtasks_l2):
            subtask_l2 = subtask_l2.strip()
            if not subtask_l2: continue
            yield f"[Status] Stage {i+1}/{len(subtasks_l1)}, Solving L2 step {j+1}/{len(subtasks_l2)}: \"{subtask_l2}...\""
            print(f"[High Mode]     Solving Level 2 step ({j+1}/{len(subtasks_l2)}): \"{subtask_l2}\"...")

            if len(subtasks_l2) == 1 and subtask_l2 == subtask_l1:
                solve_prompt_l2 = f'Original task: "{user_input}".\nCurrent Level 1 stage: "{subtask_l1}".\nThis stage could not be broken down further. Solve this specific stage in detail.'
            else:
                 solve_prompt_l2 = f'Original task: "{user_input}".\nCurrent Level 1 stage: "{subtask_l1}".\nCurrent Level 2 step: "{subtask_l2}".\nSolve this specific Level 2 step in detail.'

            result_l2_gen = call_llm(solve_prompt_l2, chat_history_gradio=temp_history_high, temperature=temperature, top_p=top_p, top_k=top_k, stream=False)
            result_l2 = next(result_l2_gen, f"Error: No response for L2 step {j+1}.")
            subtasks_l2_results.append({"subtask": subtask_l2, "result": result_l2})
            print(f"[High Mode]     Level 2 step result ({j+1}): Received.")
            if result_l2.startswith("Error:") or result_l2.startswith("Network error:"):
                yield f"[Status] Error solving L2 step {j+1} in stage {i+1}. Aborting stage..."
                print(f"[High Mode]   Error solving L2 step {j+1}: {result_l2}. Aborting stage {i+1}.")
                subtasks_l1_results.append({"subtask": subtask_l1, "result": f"[Error processing stage {i+1}: {result_l2}]"})
                abort_stage = True
                break

        if abort_stage:
            continue


        yield f"[Status] Stage {i+1}: Synthesizing results from {len(subtasks_l2)} Level 2 step(s)..."
        print(f"[High Mode]   Synthesizing Level 2 results for L1 subtask \"{subtask_l1}\"...")
        result_l1_final = ""
        if len(subtasks_l2_results) == 1:
             result_l1_final = subtasks_l2_results[0]['result']
             print(f"[High Mode]   Result for \"{subtask_l1}\" (from single L2 step): Received.")
        else:
            synthesis_prompt_l2 = f'The goal for this stage was: "{subtask_l1}". The results for the Level 2 steps taken are:\n---\n'
            for j, res_l2 in enumerate(subtasks_l2_results):
                synthesis_prompt_l2 += f"{j+1}. Step: {res_l2['subtask']}\n   Result: {res_l2['result']}\n---\n"
            synthesis_prompt_l2 += f'Synthesize these results into a single, coherent answer for the Level 1 stage: "{subtask_l1}". Focus on fulfilling the goal of this stage.'

            result_l1_final_gen = call_llm(synthesis_prompt_l2, temperature=control_temp, top_p=top_p, top_k=top_k, stream=False)
            result_l1_final = next(result_l1_final_gen, f"Error: No response for L1 synthesis stage {i+1}.")
            print(f"[High Mode]   Result for \"{subtask_l1}\" (synthesized from L2): Received.")
            if result_l1_final.startswith("Error:") or result_l1_final.startswith("Network error:"):
                 yield f"[Status] Error synthesizing L2 results for stage {i+1}. Using raw results..."
                 print(f"[High Mode]   Error synthesizing L2 results for stage {i+1}: {result_l1_final}. Using raw results.")
                 result_l1_final = "\n".join([f"Step {j+1}: {res['subtask']}\nResult: {res['result']}" for j, res in enumerate(subtasks_l2_results)])


        subtasks_l1_results.append({"subtask": subtask_l1, "result": result_l1_final})

    yield "[Status] All Level 1 stages processed. Synthesizing final response..."
    print("[High Mode] Synthesizing final response from Level 1 results (streaming)...")
    final_synthesis_prompt = f'Original complex task: "{user_input}". The task was addressed in the following major stages, with these results:\n---\n'
    for i, res_l1 in enumerate(subtasks_l1_results):
        final_synthesis_prompt += f"{i+1}. Stage: {res_l1['subtask']}\n   Overall Result for Stage: {res_l1['result']}\n---\n"
    final_synthesis_prompt += "Synthesize all these stage results into a comprehensive, well-structured final answer that directly addresses the original complex task. Ensure coherence and clarity."

    full_response = ""
    for chunk in call_llm(final_synthesis_prompt, temperature=control_temp, top_p=top_p, top_k=top_k, stream=True):
        full_response += chunk
        yield full_response
    print("[High Mode] Final response stream synthesized.")


def chat_interface_logic(message, history, compute_level, temperature, top_p, top_k):
    if history is None:
        history = []

    history.append([message, ""])
    yield history, "", "[Status] Processing request..."

    compute_function = None
    if compute_level == "Low":
        compute_function = low_compute
    elif compute_level == "Medium":
        compute_function = medium_compute
    elif compute_level == "High":
        compute_function = high_compute
    else:
        error_msg = "Error: Unknown computation level selected."
        history[-1][1] = error_msg
        yield history, "", "[Status] Error"
        return

    response_generator = compute_function(message, history[:-1], temperature, top_p, top_k)

    final_assistant_response = ""
    current_status = "[Status] Processing request..."

    try:
        for response_part in response_generator:
            if isinstance(response_part, str) and response_part.startswith("[Status]"):
                current_status = response_part
                yield history, "", current_status
            elif isinstance(response_part, str):
                final_assistant_response = response_part
                history[-1][1] = final_assistant_response
                yield history, "", current_status
            else:
                print(f"Warning: Unexpected type yielded from compute function: {type(response_part)}")
                error_fragment = f"\n[Warning: Unexpected data type in response stream: {type(response_part)}]"
                final_assistant_response += error_fragment
                history[-1][1] = final_assistant_response
                yield history, "", current_status

    except Exception as e:
        print(f"Error during response generation: {e}")
        error_msg = f"An error occurred during processing: {e}"
        history[-1][1] = error_msg
        yield history, "", "[Status] Error Encountered"
        return

    yield history, "", ""


def regenerate_last(history, compute_level, temperature, top_p, top_k):
    if not history:
        yield history, "", "[Status] Cannot regenerate: Chat history is empty."
        return

    if history[-1][0] is None or history[-1][0] == "":
         yield history, "", "[Status] Cannot regenerate: Last entry is not a user message."
         return

    last_user_message = history[-1][0]
    history_context = history[:-1]

    history[-1][1] = ""
    yield history, "", f"[Status] Regenerating response for: \"{last_user_message[:50]}...\""

    compute_function = None
    if compute_level == "Low":
        compute_function = low_compute
    elif compute_level == "Medium":
        compute_function = medium_compute
    elif compute_level == "High":
        compute_function = high_compute
    else:
        error_msg = "Error: Unknown computation level selected."
        history[-1][1] = error_msg
        yield history, "", "[Status] Error"
        return

    response_generator = compute_function(last_user_message, history_context, temperature, top_p, top_k)

    final_assistant_response = ""
    current_status = f"[Status] Regenerating response for: \"{last_user_message[:50]}...\""

    try:
        for response_part in response_generator:
            if isinstance(response_part, str) and response_part.startswith("[Status]"):
                current_status = response_part
                yield history, "", current_status
            elif isinstance(response_part, str):
                final_assistant_response = response_part
                history[-1][1] = final_assistant_response
                yield history, "", current_status
            else:
                print(f"Warning: Unexpected type yielded during regeneration: {type(response_part)}")
                error_fragment = f"\n[Warning: Unexpected data type in response stream: {type(response_part)}]"
                final_assistant_response += error_fragment
                history[-1][1] = final_assistant_response
                yield history, "", current_status

    except Exception as e:
        print(f"Error during response regeneration: {e}")
        error_msg = f"An error occurred during regeneration: {e}"
        history[-1][1] = error_msg
        yield history, "", "[Status] Error Encountered during Regeneration"
        return

    yield history, "", ""


with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Advanced Chat Agent with Computation Levels (Local LLM)")
    gr.Markdown(f"Using endpoint: `{LOCAL_API_ENDPOINT}` with model `{LLM_MODEL}`")
    if LLM_API_KEY:
        gr.Markdown("API Key: Loaded from environment variable.")
    else:
        gr.Markdown("API Key: Not configured (using endpoint without Authorization header).")

    with gr.Row():
        with gr.Column(scale=1):
            compute_level_selector = gr.Radio(
                ["Low", "Medium", "High"],
                label="Computation Level",
                value="Low",
                info="Low: Direct response. Medium: 1-level decomposition. High: 2-level decomposition."
            )
            temp_slider = gr.Slider(
                minimum=0.0, maximum=2.0, value=0.7, step=0.1, label="Temperature",
                info="Controls randomness. Lower values make the model more deterministic."
            )
            top_p_slider = gr.Slider(
                minimum=0.0, maximum=1.0, value=1.0, step=0.05, label="Top-P (Nucleus Sampling)",
                info="Considers only tokens with cumulative probability >= top_p. 1.0 disables it."
            )
            top_k_slider = gr.Slider(
                minimum=0, maximum=100, value=0, step=1, label="Top-K",
                info="Considers only the top k most likely tokens. 0 disables it."
            )
            with gr.Row():
                 regenerate_btn = gr.Button("Regenerate")
                 clear_btn = gr.ClearButton(value="Clear Chat")


        with gr.Column(scale=4):
            status_display = gr.Markdown("", label="Current Status")
            chatbot = gr.Chatbot(label="Chat", height=700, show_copy_button=True, likeable=True, show_share_button=True)
            with gr.Row():
                chat_input = gr.Textbox(
                    label="Your message",
                    placeholder="Enter your query here...",
                    scale=4,
                    show_label=False,
                    container=False
                )
                submit_btn = gr.Button("Submit", variant="primary", scale=1, min_width=120)

    clear_btn.add(components=[chat_input, chatbot, status_display])

    submit_inputs = [chat_input, chatbot, compute_level_selector, temp_slider, top_p_slider, top_k_slider]
    submit_outputs = [chatbot, chat_input, status_display]

    regenerate_inputs = [chatbot, compute_level_selector, temp_slider, top_p_slider, top_k_slider]
    regenerate_outputs = [chatbot, chat_input, status_display]

    submit_btn.click(
        fn=chat_interface_logic,
        inputs=submit_inputs,
        outputs=submit_outputs,
        queue=True
    )
    chat_input.submit(
         fn=chat_interface_logic,
        inputs=submit_inputs,
        outputs=submit_outputs,
        queue=True
    )
    regenerate_btn.click(
        fn=regenerate_last,
        inputs=regenerate_inputs,
        outputs=regenerate_outputs,
        queue=True
    )


if __name__ == "__main__":
    print(f"Launching Gradio interface for local LLM...")
    print(f"Connecting to: {LOCAL_API_ENDPOINT}")
    print(f"Model name used in requests: {LLM_MODEL}")
    if LLM_API_KEY:
        print("API Key detected in environment variables.")
    else:
        print("API Key not found in environment variables.")
    try:
        base_url = '/'.join(LOCAL_API_ENDPOINT.split('/')[:3])
        response = requests.get(base_url, timeout=5)
        print(f"Base URL {base_url} is accessible (Status: {response.status_code}).")
    except Exception as e:
        print(f"Warning: Could not check endpoint base URL accessibility ({base_url}): {e}")

    demo.launch()
