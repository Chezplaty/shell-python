class EditBuffer:

    def __init__(self) -> None:
        """
        Sets up an empty character buffer with the cursor at the start.
        """
        self.buffer = []
        self.cursor_pos = 0

    def text(self) -> str:
        """
        Returns the buffer's contents as a single string.
        """
        return "".join(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)

    def insert(self, key: str) -> None:
        """
        Appends a character to the buffer and advances the cursor.
        """
        self.buffer.append(key)
        self.cursor_pos += 1

    def backspace(self) -> bool:
        """
        Removes the last character from the buffer, if any.
        Returns whether a character was removed.
        """
        if not self.buffer:
            return False

        self.buffer.pop()
        self.cursor_pos -= 1
        return True

    def move_left(self) -> bool:
        """
        Moves the cursor one position left, if possible.
        Returns whether the cursor moved.
        """
        if self.cursor_pos <= 0:
            return False

        self.cursor_pos -= 1
        return True

    def move_right(self) -> bool:
        """
        Moves the cursor one position right, if possible.
        Returns whether the cursor moved.
        """
        if self.cursor_pos >= len(self.buffer):
            return False

        self.cursor_pos += 1
        return True

    def up_down_arrow(self, hist_man: HistoryManager, direction: int) -> tuple[str | str] | tuple[None | None]:
        """
        Replace the current buffer with a previous or next history entry.
        If there is no previous or next entry, return None.
        """

        line = hist_man.get_next_line(direction)
        if line is None:
            return (None, None)

        old_text = self.text()
        self.replace_buffer(len(old_text), line)

        return old_text, line
    
    def replace_buffer(self, old_len: int, new_text: str) -> None:
        """
        Removes the last old_len characters from the buffer and appends new_text in their place.
        """
        if old_len:
            del self.buffer[-old_len:]

        self.buffer.extend(new_text)
        self.cursor_pos += len(new_text) - old_len

