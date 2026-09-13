"""
Lex Go-template actions and literal output for discovery and symbolic compilation.
"""

from attrs import frozen

SPACE = " \t\r\n"


@frozen
class Token:
    """
    Retain literal text or a complete template action after lexical whitespace trimming.

    Attributes:
        action (bool): Whether this token contains an action rather than literal output.
        text (str): Complete token content.
        line (int): Original source line.
    """

    action: bool
    text: str
    line: int


def lex(source: str) -> list[Token]:
    """
    Preserve text and honor Go trim markers, quoted delimiters and block comments.

    Args:
        source (str): Complete template source.

    Returns:
        list[Token]: Lossless output fragments and complete actions.
    """
    tokens: list[Token] = []
    position = 0
    trim = False
    while True:
        start = source.find("{{", position)
        stop = len(source) if start < 0 else start
        literal = source[position:stop]
        if trim:
            literal = literal.lstrip(SPACE)
        line = source.count("\n", 0, position) + 1
        if start < 0:
            tokens.append(Token(False, literal, line))
            return tokens
        cursor = start + 2
        left = source[cursor : cursor + 1] == "-" and source[cursor + 1 : cursor + 2] in tuple(SPACE)
        if left:
            literal = literal.rstrip(SPACE)
        tokens.append(Token(False, literal, line))
        quote = ""
        comment = False
        while cursor < len(source):
            if comment:
                if source.startswith("*/", cursor):
                    comment = False
                    cursor += 2
                    continue
            elif quote:
                if source[cursor] == "\\" and quote != "`":
                    cursor += 2
                    continue
                if source[cursor] == quote:
                    quote = ""
            elif source.startswith("/*", cursor):
                comment = True
                cursor += 2
                continue
            elif source[cursor] in ('"', "`", "'"):
                quote = source[cursor]
            elif source.startswith("}}", cursor):
                break
            cursor += 1
        if cursor >= len(source):
            raise ValueError("unterminated template action")
        action = source[start + 2 : cursor]
        trim = len(action) >= 2 and action[-1] == "-" and action[-2] in SPACE
        if left:
            action = action[1:]
        if trim:
            action = action[:-1]
        action = action.strip(SPACE)
        if not (action.startswith("/*") and action.endswith("*/")):
            tokens.append(Token(True, action, source.count("\n", 0, start) + 1))
        position = cursor + 2
