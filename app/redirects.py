from app.lexer import TokenType
from app.errors import BuiltinError


#TODO: check between access denied and target just being a directory
def apply_redirections(instruction: Instruction) -> None:
    """
    Applies the output redirections specified by an instruction before command execution.
    Raises a BuiltinError if a redirection target cannot be opened or written to.
    """

    for redirect in instruction.redirects:

        if redirect.type == TokenType.OVERWRITE:
            try:
                with open(redirect.target, "w") as file:
                    file.write(" ".join(instruction.args))

            except OSError as e:
                raise BuiltinError(instruction.cmd, f"{redirect.target}: {e.strerror}") from e