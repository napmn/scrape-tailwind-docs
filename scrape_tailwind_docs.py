import asyncio
import re
import os

import lxml.html as html
import aiohttp

EXTRA_SPACES_NUM = 4
HORIZONTAL_DELIM_LENGTH = 150
IGNORED_SECTIONS = [
    'Getting started',
    'Core Concepts',
    'Customization',
    'Base Styles',
    'Official Plugins'
]
EMOJIS_PATTERN = re.compile("[" u"\U0001F600-\U0001F64F" "]+", re.UNICODE)


async def get_tailwind_doc_links_schema(session):
    async with session.get('https://v2.tailwindcss.com/docs') as response:
        response_text = await response.text()
        doc = html.fromstring(response_text)
        schema = {}
        sections = doc.xpath('//h5')
        for section in sections:
            section_links = {}
            section_anchors = section.xpath('./following::ul[1]/*/a')
            for anchor in section_anchors:
                section_links[anchor.text_content()] = {
                    'url_path': anchor.attrib["href"]
                }
            schema[section.text] = section_links
        return schema


async def get_item_data(session, section_name, name, url_path):
    async with session.get(f'https://v2.tailwindcss.com{url_path}') as response:
        response_text = await response.text()
        doc = html.fromstring(re.sub(EMOJIS_PATTERN, '', response_text))
        description = '**' + doc.xpath('//p[@class="mt-1 text-lg text-gray-500"]')[0].text + '**'
        properties_table = doc.xpath('//table[./thead/tr/th/div[text()="Class"]]')[0]
        rows = properties_table.xpath('./tbody/tr')
        parsed_properties = []
        for row in rows:
            parsed_properties.append(tuple(row.xpath('./td/text()')[:2]))

        max_cls_len = max(len(prop[0]) for prop in parsed_properties)
        max_plus_extra = max_cls_len + EXTRA_SPACES_NUM

        rows = []
        border = ('| ' + '-' * max_plus_extra + ' | ') + ('-' * HORIZONTAL_DELIM_LENGTH + ' |')
        for property in parsed_properties:
            row = border
            row += f'\n| {property[0].ljust(max_plus_extra)} |'
            # +2 is for padding around |
            formatted_property = property[1].replace(
                '\n', '\n|' + ' ' * (max_plus_extra + 2) + '| '
            )
            row += f' {formatted_property}'
            rows.append(row)

        str_rows = '\n'.join(rows)
        formatted_content = f'#{name.upper()}\n\n{description}'\
            f'\n\n{str_rows}\n{border}\n'

        return section_name, name, formatted_content


def output_tailwind_docs(results):
    for section_name, name, formatted_content in results:
        section_path = f'tailwind_docs/{section_name.replace(" ", "_")}'
        os.makedirs(section_path, exist_ok=True)
        with open(f'{section_path}/{name.replace(" / ", "-").replace(" ", "_")}.md', 'w') as f:
            f.write(formatted_content)


async def main():
    async with aiohttp.ClientSession() as session:
        schema = await get_tailwind_doc_links_schema(session)
        futures = []
        for section_name, section_items in schema.items():
            if section_name in IGNORED_SECTIONS:
                continue
            for name, data in section_items.items():
                print(f'Fetching docs for {name}')
                futures.append(get_item_data(session, section_name, name, data['url_path']))
        results = await asyncio.gather(*futures)
    output_tailwind_docs(results)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
