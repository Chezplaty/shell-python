
class BuiltinError(Exception):
    def __init__(self, cmd: str, message: str):
        self.cmd = cmd
        self.message = message
    
    def __str__(self):
        return f"{self.cmd}: {self.message}"

class ParseError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message

