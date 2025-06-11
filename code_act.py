import re
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

from codesandbox.sandbox_manager import PythonSandboxManager

BACKTICK_PATTERN = r"(?:^|\n)```(.*?)(?:```(?:\n|$))"


class AgentState(TypedDict):
    """State for the codeact agent."""

    messages: Annotated[list[AnyMessage], add_messages]
    code_blocks: list[str]


def extract_and_combine_codeblocks(text: str) -> str:
    """Extracts all codeblocks from a text string and combines them into a single code string.

    Args:
        text: A string containing zero or more codeblocks, where each codeblock is
            surrounded by triple backticks (```).

    Returns:
        A string containing the combined code from all codeblocks, with each codeblock
        separated by a newline.

    Example:
        text = '''Here's some code:

        ```python
        print('hello')
        ```
        And more:

        ```
        print('world')
        ```'''

        result = extract_and_combine_codeblocks(text)

        Result:

        print('hello')

        print('world')

    """
    # Find all code blocks in the text using regex
    # Pattern matches anything between triple backticks, with or without a language identifier
    code_blocks = re.findall(BACKTICK_PATTERN, text, re.DOTALL)

    if not code_blocks:
        return ""

    # Process each codeblock
    processed_blocks = []
    for block in code_blocks:
        # Strip leading and trailing whitespace
        block = block.strip()

        # If the first line looks like a language identifier, remove it
        lines = block.split("\n")
        if lines and (not lines[0].strip() or " " not in lines[0].strip()):
            # First line is empty or likely a language identifier (no spaces)
            block = "\n".join(lines[1:])

        processed_blocks.append(block)

    # Combine all codeblocks with newlines between them
    combined_code = "\n\n".join(processed_blocks)
    return combined_code


def call_model(state: AgentState) -> Command:
    response = llm.invoke(state["messages"])
    code = extract_and_combine_codeblocks(response.content)
    if code:
        return Command(goto="run_sandbox", update={"messages": [response], "code_blocks": [code]})
    else:
        return Command(update={"messages": [response]})


def run_sandbox(state: AgentState) -> dict:
    # Ensure sandbox is running (restart if needed)
    if not sandbox_manager.is_running:
        print("🔄 Restarting sandbox container...")
        sandbox_manager.restart_container()

    # For conversational agents, we may want to be more lenient with errors
    # and only shutdown on critical failures (timeouts, container issues)
    execution = sandbox_manager.run(
        state["code_blocks"][-1],
        shutdown_on_failure=False,  # Let the agent handle errors gracefully
    )

    stdout = execution.stdout
    stderr = execution.stderr

    # Check for critical failures that should stop the conversation
    if execution.exit_code == 124:  # Timeout
        result = f"⚠️ Code execution timed out. The sandbox has been shut down for safety.\n\nError: {execution.error}"
        # Manually shutdown on timeout
        if sandbox_manager.is_running:
            sandbox_manager.stop_container()
    elif execution.error and "Execution failed:" in execution.error:  # Critical system error
        result = f"❌ Critical execution failure. The sandbox has been shut down.\n\nError: {execution.error}"
        # Manually shutdown on critical error
        if sandbox_manager.is_running:
            sandbox_manager.stop_container()
    elif stderr.strip():
        # Enhanced error reporting for better agent debugging
        error_type = "Unknown Error"
        debugging_hint = ""

        # Analyze the error type for helpful hints
        stderr_lower = stderr.lower()
        if "syntaxerror" in stderr_lower:
            error_type = "Syntax Error"
            debugging_hint = (
                "\n💡 Debugging hint: Check for missing parentheses, quotes, or colons. Review Python syntax rules."
            )
        elif "nameerror" in stderr_lower:
            error_type = "Name Error"
            debugging_hint = "\n💡 Debugging hint: A variable or function is not defined. Make sure to define variables before using them."
        elif "zerodivisionerror" in stderr_lower:
            error_type = "Division by Zero Error"
            debugging_hint = "\n💡 Debugging hint: Add a check to ensure the denominator is not zero before division."
        elif "importerror" in stderr_lower or "modulenotfounderror" in stderr_lower:
            error_type = "Import Error"
            debugging_hint = "\n💡 Debugging hint: The module doesn't exist or isn't installed. Check the module name or install it if needed."
        elif "indentationerror" in stderr_lower:
            error_type = "Indentation Error"
            debugging_hint = "\n💡 Debugging hint: Check your code indentation. Python uses consistent indentation to define code blocks."
        elif "typeerror" in stderr_lower:
            error_type = "Type Error"
            debugging_hint = "\n💡 Debugging hint: There's a mismatch between expected and actual data types. Check your variable types."
        elif "keyerror" in stderr_lower:
            error_type = "Key Error"
            debugging_hint = "\n💡 Debugging hint: Trying to access a dictionary key that doesn't exist. Check if the key exists first."
        elif "indexerror" in stderr_lower:
            error_type = "Index Error"
            debugging_hint = (
                "\n💡 Debugging hint: List index is out of range. Check the list length before accessing indices."
            )

        result = f"❌ {error_type} occurred during execution:\n\nStdout:\n{stdout}\n\nStderr:\n{stderr}{debugging_hint}"
    else:
        result = f"✅ Execution completed successfully:\n\n{stdout}"

    return {"messages": [HumanMessage(content=result)]}


if __name__ == "__main__":
    llm = init_chat_model(model="gemini-2.5-flash-preview-05-20", model_provider="google_genai")

    system_prompt = """
You are a helpful assistant that can write Python code to solve problems.
The code you write will be executed in a sandbox and the results will be fed back to you for evaluation.

IMPORTANT GUIDELINES:
1. **State Persistence**: Variables, functions, and imports persist between code executions in the same session.
2. **Output**: Use print statements to display results since only stdout is visible to the user.
3. **Error Handling**: If you receive an error, analyze it carefully and try to fix the issue in your next code attempt.
4. **Debugging**: When errors occur, you'll receive the full error traceback plus debugging hints to help you fix issues.
5. **No main blocks**: Don't use 'if __name__ == "__main__"' blocks.
6. **Code Quality**: Write clear, well-commented code that handles edge cases appropriately.

DEBUGGING WORKFLOW:
- If you get a SyntaxError: Check for missing parentheses, quotes, or proper indentation
- If you get a NameError: Define the missing variable or import the missing module
- If you get a TypeError: Check data types and function arguments
- If you get runtime errors: Add proper error handling and validation

After running code, provide a summary of the results and how they address the user's request. If errors occur, explain what went wrong and how you'll fix it in the next attempt.
"""

    # sandbox = PythonSandboxManager()
    # sandbox.start_container()
    # Create sandbox manager instance with WRITABLE directory
    with PythonSandboxManager().configure_context_manager(
        expose_directories_rw={"/Users/carli/Projects/code_sandbox/vault": "/app/output"}
    ) as sandbox_manager:
        # Define the graph of execution
        agent = StateGraph(AgentState)
        agent.add_node("call_model", call_model)
        agent.add_node("run_sandbox", run_sandbox)
        agent.add_edge(START, "call_model")
        agent.add_edge("run_sandbox", "call_model")
        compiled_agent = agent.compile()

        starting_state = {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content="Write a python function to estimate pi using the Monte Carlo method. Save the result in the file /app/output/pi.txt"
                ),
            ]
        }

        result = compiled_agent.invoke(starting_state)
        # print("Final result:", result)

        result["messages"][-1].pretty_print()
