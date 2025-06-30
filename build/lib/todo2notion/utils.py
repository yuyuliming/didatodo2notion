import calendar
from datetime import datetime
from datetime import timedelta
import hashlib
import os
import re
import requests
import emoji


import os, re, glob, base64, json
from notion_client import Client
from os import environ
from todo2notion.config import (
    RICH_TEXT,
    URL,
    RELATION,
    NUMBER,
    DATE,
    FILES,
    STATUS,
    TITLE,
    SELECT,
    MULTI_SELECT,
    TZ
)
import pendulum

MAX_LENGTH = (
    1024  # NOTION 2000个字符限制https://developers.notion.com/reference/request-limits
)


def get_heading(level, content):
    if level == 1:
        heading = "heading_1"
    elif level == 2:
        heading = "heading_2"
    else:
        heading = "heading_3"
    return {
        "type": heading,
        heading: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": content[:MAX_LENGTH],
                    },
                }
            ],
            "color": "default",
            "is_toggleable": False,
        },
    }


def get_table_of_contents():
    """获取目录"""
    return {"type": "table_of_contents", "table_of_contents": {"color": "default"}}


def get_title(content):
    return {"title": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}]}


def get_rich_text(content):
    return {"rich_text": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}]}


def get_url(url):
    return {"url": url}


def get_file(url):
    return {"files": [{"type": "external", "name": "Cover", "external": {"url": url}}]}


def get_multi_select(names):
    return {"multi_select": [{"name": name} for name in names]}


def get_relation(ids):
    return {"relation": [{"id": id} for id in ids]}


def get_date(start, end=None):
    return {
        "date": {
            "start": start,
            "end": end,
            "time_zone": "Asia/Shanghai",
        }
    }


def get_icon(url):
    return {"type": "external", "external": {"url": url}}


def get_select(name):
    return {"select": {"name": name}}


def get_number(number):
    return {"number": number}


def get_quote(content):
    return {
        "type": "quote",
        "quote": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": content[:MAX_LENGTH]},
                }
            ],
            "color": "default",
        },
    }



def get_rich_text_from_result(result, name):
    return result.get("properties").get(name).get("rich_text")[0].get("plain_text")


def get_number_from_result(result, name):
    return result.get("properties").get(name).get("number")


def format_time(time):
    """将秒格式化为 xx时xx分格式"""
    result = ""
    hour = time // 3600
    if hour > 0:
        result += f"{hour}时"
    minutes = time % 3600 // 60
    if minutes > 0:
        result += f"{minutes}分"
    return result


def format_date(date, format="%Y-%m-%d %H:%M:%S"):
    return date.strftime(format)


def timestamp_to_date(timestamp):
    """时间戳转化为date"""
    return datetime.utcfromtimestamp(timestamp) + timedelta(hours=8)


def get_first_and_last_day_of_month(date):
    # 获取给定日期所在月的第一天
    first_day = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 获取给定日期所在月的最后一天
    _, last_day_of_month = calendar.monthrange(date.year, date.month)
    last_day = date.replace(
        day=last_day_of_month, hour=0, minute=0, second=0, microsecond=0
    )

    return first_day, last_day


def get_first_and_last_day_of_year(date):
    # 获取给定日期所在年的第一天
    first_day = date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # 获取给定日期所在年的最后一天
    last_day = date.replace(month=12, day=31, hour=0, minute=0, second=0, microsecond=0)

    return first_day, last_day


def get_first_and_last_day_of_week(date):
    # 获取给定日期所在周的第一天（星期一）
    first_day_of_week = (date - timedelta(days=date.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # 获取给定日期所在周的最后一天（星期日）
    last_day_of_week = first_day_of_week + timedelta(days=7) 

    return first_day_of_week, last_day_of_week


def get_properties(dict1, dict2):
    properties = {}
    for key, value in dict1.items():
        type = dict2.get(key)
        if value == None:
            continue
        property = None
        if type == TITLE:
            property = {
                "title": [
                    {"type": "text", "text": {"content": value[:MAX_LENGTH]}}
                ]
            }
        elif type == RICH_TEXT:
            property = {
                "rich_text": [
                    {"type": "text", "text": {"content": value[:MAX_LENGTH]}}
                ]
            }
        elif type == NUMBER:
            property = {"number": value}
        elif type == STATUS:
            property = {"status": {"name": value}}
        elif type == FILES:
            property = {"files": [{"type": "external", "name": "Cover", "external": {"url": value}}]}
        elif type == DATE:
            property = {
                "date": {
                    "start": pendulum.from_timestamp(
                        value, tz="Asia/Shanghai"
                    ).to_datetime_string(),
                    "time_zone": "Asia/Shanghai",
                }
            }
        elif type==URL:
            property = {"url": value}        
        elif type==SELECT:
            property = {"select": {"name": value}}        
        elif type==MULTI_SELECT:
            property = {"multi_select": [{"name": name} for name in value]}
        elif type == RELATION:
            property = {"relation": [{"id": id} for id in value]}
        elif type =="people":
            property = {"people": [{"id": item.get("id"),"object":item.get("object")} for item in value]}
        if property:
            properties[key] = property
    return properties


def get_property_value(property):
    """从Property中获取值"""
    type = property.get("type")
    content = property.get(type)
    if content is None:
        return None
    if type == "title" or type == "rich_text":
        if(len(content)>0):
            return content[0].get("plain_text")
        else:
            return None
    elif type == "status" or type == "select":
        return content.get("name")
    elif type == "files":
        # 不考虑多文件情况
        if len(content) > 0 and content[0].get("type") == "external":
            return content[0].get("external").get("url")
        else:
            return None
    elif type == "date":
        return str_to_timestamp(content.get("start"))
    else:
        return content


def calculate_book_str_id(book_id):
    md5 = hashlib.md5()
    md5.update(book_id.encode("utf-8"))
    digest = md5.hexdigest()
    result = digest[0:3]
    code, transformed_ids = transform_id(book_id)
    result += code + "2" + digest[-2:]

    for i in range(len(transformed_ids)):
        hex_length_str = format(len(transformed_ids[i]), "x")
        if len(hex_length_str) == 1:
            hex_length_str = "0" + hex_length_str

        result += hex_length_str + transformed_ids[i]

        if i < len(transformed_ids) - 1:
            result += "g"

    if len(result) < 20:
        result += digest[0 : 20 - len(result)]
    md5 = hashlib.md5()
    md5.update(result.encode("utf-8"))
    result += md5.hexdigest()[0:3]
    return result

def transform_id(book_id):
    id_length = len(book_id)
    if re.match("^\d*$", book_id):
        ary = []
        for i in range(0, id_length, 9):
            ary.append(format(int(book_id[i : min(i + 9, id_length)]), "x"))
        return "3", ary

    result = ""
    for i in range(id_length):
        result += format(ord(book_id[i]), "x")
    return "4", [result]

def get_weread_url(book_id):
    return f"https://weread.qq.com/web/reader/{calculate_book_str_id(book_id)}"

def str_to_timestamp(date):
    if date == None:
        return 0
    dt = pendulum.parse(date)
    # 获取时间戳
    return int(dt.timestamp())


def url_to_md5(url):
    # 创建一个md5哈希对象
    md5_hash = hashlib.md5()

    # 对URL进行编码，准备进行哈希处理
    # 默认使用utf-8编码
    encoded_url = url.encode('utf-8')

    # 更新哈希对象的状态
    md5_hash.update(encoded_url)

    # 获取十六进制的哈希表示
    hex_digest = md5_hash.hexdigest()

    return hex_digest

def download_image(url, save_dir="cover"):
    # 确保目录存在，如果不存在则创建
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    file_name = url_to_md5(url) + ".jpg"
    save_path = os.path.join(save_dir, file_name)

    # 检查文件是否已经存在，如果存在则不进行下载
    if os.path.exists(save_path):
        print(f"File {file_name} already exists. Skipping download.")
        return save_path

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
        print(f"Image downloaded successfully to {save_path}")
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
    return save_path

def parse_date(date_str):
        # get_task()
    return pendulum.parse(date_str).int_timestamp

def split_emoji_from_string(s):
    # 检查第一个字符是否是emoji
    l = list(filter(lambda x: x.get("match_start")==0,emoji.emoji_list(s)))
    if len(l)>0:
        # 如果整个字符串都是emoji
        return l[0].get("emoji"), s[l[0].get("match_end"):]
    else:
        # 如果字符串不是以emoji开头
        return '✅', s


def replace_part(parts, pattern, replace_function):
    # Process italic matches
    new_text_parts = []
    for part in parts:
        if isinstance(part, str):
            matches = list(re.finditer(pattern, part))
            prev_end = 0
            for match in matches:
                if prev_end != match.start():
                    new_text_parts.append(part[prev_end:match.start()])
                new_text_parts.append(replace_function(match))
                prev_end = match.end()
            new_text_parts.append(part[prev_end:])
        else:
            new_text_parts.append(part)
    return new_text_parts

def process_inline_formatting(text):
    """
    Process inline formatting in Markdown text and convert it to Notion rich text formatting.

    :param text: The Markdown text to be processed.
    :type text: str
    :return: A list of Notion rich text objects representing the processed text.
    :rtype: list
    """

    # Regular expressions for bold and italic markdown
    code_pattern = r'`(.+?)`'
    bold_pattern = r'(\*\*(.+?)\*\*)|(__(.+?)__)'
    overline_pattern = r'\~(.+?)\~'
    inline_katex_pattern = r'\$(.+?)\$'
    italic_pattern = r'(\*(.+?)\*)|(_(.+?)_)'
    link_pattern = r'\[(.+?)\]\((.+?)\)'
    bold_italic_pattern = r'(__\*(.+?)\*__)|(\*\*_(.+?)_\*\*)'

    def replace_katex(match):
        return {
            "type": "equation",
            "equation": {
                "expression": match.group(1)
            }
        }

    def replace_bolditalic(match):
        content = match.group(2) or match.group(4)
        return {
            "type": "text",
            "text": {
                "content": content,
                "link": None
            },
            "annotations": {
                "bold": True,
                "italic": True,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default"
            },
            "plain_text": content,
            "href": None
        }

    # Replace markdown with Notion rich text formatting
    def replace_code(match):
        return {
            "type": "text",
            "text": {
                "content": match.group(1),
                "link": None
            },
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": True,
                "color": "default"
            },
            "plain_text": match.group(1),
            "href": None
        }

    # Replace markdown with Notion rich text formatting
    def replace_overline(match):
        return {
            "type": "text",
            "text": {
                "content": match.group(1),
                "link": None
            },
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": True,
                "underline": False,
                "code": False,
                "color": "default"
            },
            "plain_text": match.group(1),
            "href": None
        }
    # Replace markdown with Notion rich text formatting
    def replace_bold(match):
        return {
            "type": "text",
            "text": {
                "content": match.group(2) or match.group(4),
                "link": None
            },
            "annotations": {
                "bold": True,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default"
            },
            "plain_text": match.group(2) or match.group(4),
            "href": None
        }

    def replace_italic(match):
        return {
            "type": "text",
            "text": {
                "content": match.group(2) or match.group(4),
                "link": None
            },
            "annotations": {
                "bold": False,
                "italic": True,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default"
            },
            "plain_text": match.group(2) or match.group(4),
            "href": None
        }

    def replace_link(match):
        return {
            "type": "text",
            "text": {
                "content": match.group(1),
                "link": {
                    "url": match.group(2)
                }
            },
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default"
            },
            "plain_text": match.group(1),
            "href": match.group(2)
        }

    # Apply the replacements for bold and italic formatting
    text_parts = []

    # Process bold italic matches
    matches = list(re.finditer(bold_italic_pattern, text))
    prev_end = 0
    for match in matches:
        if prev_end != match.start():
            text_parts.append(text[prev_end:match.start()])
        text_parts.append(replace_bolditalic(match))
        prev_end = match.end()
    text_parts.append(text[prev_end:])

    text_parts = replace_part(text_parts, bold_pattern, replace_bold)
    text_parts = replace_part(text_parts, italic_pattern, replace_italic)
    text_parts = replace_part(text_parts, inline_katex_pattern, replace_katex)
    text_parts = replace_part(text_parts, overline_pattern, replace_overline)
    text_parts = replace_part(text_parts, code_pattern, replace_code)
    text_parts = replace_part(text_parts, link_pattern, replace_link)

    # Remove empty strings from the list and return the processed text parts
    return [({"type": "text", "text": {"content": part}} if type(part) == str else part) for part in text_parts if part != '']

# katex
def convert_markdown_table_to_latex(text):
    split_column = text.split('\n')
    has_header = False
    # Check if the second line is a delimiter
    if re.match(r'\|\s*-+\s*\|', split_column[1]):
        # Remove the delimiter line
        split_column.pop(1)
        has_header = True
    table_content = ""
    for i, row in enumerate(split_column):
        modified_content = re.findall(r'(?<=\|).*?(?=\|)', row)
        new_text = ""
        for j, cell in enumerate(modified_content):
            cell_text = f"\\textsf{{{cell.strip()}}}"
            if i == 0 and has_header:
                cell_text = f"\\textsf{{\\textbf{{{cell.strip()}}}}}"
            if j == len(modified_content) - 1:
                cell_text += " \\\\\\hline\n"
            else:
                cell_text += " & "
            new_text += cell_text
        table_content += new_text

    count_column = len(split_column[0].split('|'))

    table_column = "|c" * count_column
    add_table = f"\\def\\arraystretch{{1.4}}\\begin{{array}}{{{table_column}|}}\\hline\n{table_content}\\end{{array}}"

    return add_table

def parse_markdown_to_notion_blocks(markdown):
    """
    Parse Markdown text and convert it into a list of Notion blocks.

    :param markdown: The Markdown text to be parsed.
    :type markdown: str
    :return: A list of Notion blocks representing the parsed Markdown content.
    :rtype: list
    """

    # Detect code blocks enclosed within triple backticks
    code_block_pattern = re.compile(r'```(\w+?)\n(.+?)```', re.DOTALL)
    # katex
    latex_block_pattern = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
    numbered_list_pattern_nested = r'^( *)(\d+)\. '
    unordered_list_pattern_nested = r'^( *)(\-) '
    heading_pattern = r'^(#+) '

    #indented_code_pattern = re.compile(r'^ {4}(.+)$', re.MULTILINE)
    triple_backtick_code_pattern = re.compile(r'^```(.+?)```', re.MULTILINE | re.DOTALL)
    blockquote_pattern = r'^> (.+)$'
    horizontal_line_pattern = r'^-{3,}$'
    image_pattern = r'!\[(.*?)\]\((.*?)\)'

    code_blocks = {}
    def replace_code_blocks(match):
        index = len(code_blocks)
        language, content = match.group(1), match.group(2)
        code_blocks[index] = (language or 'plain text').strip(), content.strip()
        return f'CODE_BLOCK_{index}'

    # Replace code blocks with placeholders
    markdown = code_block_pattern.sub(replace_code_blocks, markdown)

    # katex
    latex_blocks = {}
    def replace_latex_blocks(match):
        index = len(latex_blocks)
        latex_blocks[index] = (match.group(1)+"").strip()
        return f'LATEX_BLOCK_{index}'

    # Replace code blocks with placeholders
    markdown = latex_block_pattern.sub(replace_latex_blocks, markdown)

    lines = markdown.split("\n")
    blocks = []

    # Initialize variables to keep track of the current table
    current_table = []
    in_table = False

    current_indent = 0
    stack = [blocks]

    indented_code_accumulator = []
    for line in lines:

        # Check if the line is a table row (e.g., "| Header 1 | Header 2 |" or "| Content 1 | Content 2 |")
        is_table_row = re.match(r'\|\s*[^-|]+\s*\|', line)
        # Check if the line is a table delimiter (e.g., "|---|---|")
        is_table_delimiter = re.match(r'\|\s*[-]+\s*\|\s*[-]+\s*\|', line)

        # If we find table row or delimiter, add the line to the current table
        if is_table_row or is_table_delimiter:
            current_table.append(line)
            in_table = True
            continue
        elif in_table and (not is_table_row and not is_table_delimiter):
            # If we find a non-table line and we're in a table, end the current table
            in_table = False
            # Process the current table
            table_str = "\n".join(current_table)
            # katex
            latex_table = convert_markdown_table_to_latex(table_str)
            # Create Notion equation block with LaTeX table expression
            equation_block = {
                "type": "equation",
                "equation": {
                    "expression": latex_table
                }
            }
            blocks.append(equation_block)
            # Reset the current table
            current_table = []
            continue

        list_match = re.match(numbered_list_pattern_nested, line)
        if list_match:
            indent = len(list_match.group(1))
            line = line[len(list_match.group(0)):]

            item = {
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": process_inline_formatting(line)
                }
            }

            while indent < current_indent:
                # If the indentation is less than the current level, go back one level in the stack
                stack.pop()
                current_indent -= 1

            if indent == current_indent:
                # Same level of indentation, add to the current level of the stack
                stack[-1].append(item)
            else: # indent > current_indent
                # Nested item, add it as a child of the previous item
                if 'children' not in stack[-1][-1]['numbered_list_item']:
                    stack[-1][-1]['numbered_list_item']['children'] = []
                stack[-1][-1]['numbered_list_item']['children'].append(item)
                stack.append(stack[-1][-1]['numbered_list_item']['children']) # Add a new level to the stack
                current_indent += 1

            continue

        list_match = re.match(unordered_list_pattern_nested, line)
        if list_match:
            indent = len(list_match.group(1))
            line = line[len(list_match.group(0)):]

            item = {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": process_inline_formatting(line)
                }
            }

            while indent < current_indent:
                # If the indentation is less than the current level, go back one level in the stack
                stack.pop()
                current_indent -= 1

            if indent == current_indent:
                # Same level of indentation, add to the current level of the stack
                stack[-1].append(item)
            else: # indent > current_indent
                # Nested item, add it as a child of the previous item
                if 'children' not in stack[-1][-1]['bulleted_list_item']:
                    stack[-1][-1]['bulleted_list_item']['children'] = []
                stack[-1][-1]['bulleted_list_item']['children'].append(item)
                stack.append(stack[-1][-1]['bulleted_list_item']['children']) # Add a new level to the stack
                current_indent += 1

            continue

        if line.startswith('    '):  # Check if the line is indented
            indented_code_accumulator.append(line[4:])  # Remove the leading spaces
            continue
        else:
            if indented_code_accumulator:  # Check if there are accumulated lines
                code_block = '\n'.join(indented_code_accumulator)
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"type": "text", "text": {"content": code_block}}]
                    }
                })
                # Clear the accumulator
                indented_code_accumulator = []

        # Check for headings and create appropriate heading blocks
        heading_match = re.match(heading_pattern, line)
        blockquote_match = re.match(blockquote_pattern, line)
        image_match = re.search(image_pattern, line)

        if heading_match:
            heading_level = len(heading_match.group(1))
            content = re.sub(heading_pattern, '', line)
            if 1 <= heading_level <= 3:
                block_type = f"heading_{heading_level}"
                blocks.append({
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": process_inline_formatting(content)
                    }
                })

        # Check for horizontal line and create divider blocks
        elif re.match(horizontal_line_pattern, line):
            blocks.append({
                "divider": {},
                "type": "divider"
            })

        # Check for blockquote and create blockquote blocks
        elif blockquote_match:
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": process_inline_formatting(blockquote_match.group(1))
                }
            })

        # Check for code blocks and create code blocks
        elif line.startswith("CODE_BLOCK_"):
            code_block_index = int(line[len("CODE_BLOCK_"):])
            language, code_block = code_blocks[code_block_index]
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": language,
                    "rich_text": [{"type": "text", "text": {"content": code_block}}]
                }
            })

        # Check for katex blocks
        elif line.startswith("LATEX_BLOCK_"):
            latex_block_index = int(line[len("LATEX_BLOCK_"):])
            latex_content = latex_blocks[latex_block_index]
            blocks.append({
                "type": "equation",
                "equation": {
                    "expression": latex_content
                }
            })

        # Image blocks
        elif image_match:
            block = {
              "object": "block",
              "type": "image",
              "image": {
                "external":{
                    "url": image_match.group(2),
                }
              }
            }
            caption = image_match.group(1)
            if caption:
                block["image"]["caption"] = [
                  {
                    "type": "text",
                    "text": {
                      "content": caption,
                      "link": None
                    }
                  }
                ]
            blocks.append(block)

        # Create paragraph blocks for other lines
        elif line.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": process_inline_formatting(line)
                }
            })

    # If there's an unfinished table at the end of the lines, process it
    if in_table:
        table_str = "\n".join(current_table)
        latex_table = convert_markdown_table_to_latex(table_str)
        equation_block = {
            "type": "equation",
            "equation": {
                "expression": latex_table
            }
        }
        blocks.append(equation_block)

    # Add any remaining indented lines as a code block
    if indented_code_accumulator:
        code_block = '\n'.join(indented_code_accumulator)
        blocks.append({
            "object": "block",
            "type": "code",
            "code": {
                "language": "plain text",
                "rich_text": [{"type": "text", "text": {"content": code_block}}]
            }
        })

    return blocks

def parse_md(markdown_text):
    """
    Parse Markdown text and convert it into Notion blocks.

    :param markdown_text: The Markdown text to be parsed.
    :type markdown_text: str
    :return: A list of Notion blocks representing the parsed Markdown content.
    :rtype: list
    """
    # Parse the transformed Markdown to create Notion blocks
    return parse_markdown_to_notion_blocks(markdown_text.strip())
