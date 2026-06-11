import json
from bs4 import BeautifulSoup, NavigableString, Comment, Doctype

_INLINE_TAGS = {'b', 'i', 'strong', 'em', 'span', 'a', 'sup', 'sub', 'br', 'u'}
_BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'blockquote', 'figcaption'}

def _has_block_children(tag) -> bool:
    for child in tag.children:
        if child.name and child.name not in _INLINE_TAGS:
            return True
    return False

def inject_translation_ids(html: str) -> str:
    """Parse HTML and restructure leaf blocks into side-by-side translation rows."""
    soup = BeautifulSoup(html, 'html.parser')
    trans_id = 0

    def wrap_block(tag):
        nonlocal trans_id
        if tag.get('data-trans-id'):
            return
            
        wrapper = soup.new_tag('div', attrs={'class': 'translation-row', 'data-trans-id': f'trans_{trans_id}', 'style': 'display: flex; flex-direction: row; width: 100%; align-items: stretch; margin-bottom: 0.5em;'})
        orig_container = soup.new_tag('div', attrs={'class': 'track-original track-it', 'style': 'flex: 1; min-width: 0;'})
        trans_container = soup.new_tag('div', attrs={'class': 'track-translation track-en', 'style': 'flex: 1; min-width: 0;'})
        
        tag.wrap(orig_container)
        orig_container.wrap(wrapper)
        wrapper.append(trans_container)
        trans_id += 1

    # 1. Standard block tags
    for tag in soup.find_all(list(_BLOCK_TAGS)):
        if tag.get_text(strip=True) and not _has_block_children(tag):
            wrap_block(tag)

    # 2. Divs that act as leaf blocks (contain no other block elements)
    for div in soup.find_all('div'):
        if not div.get('class') or 'translation-row' not in div.get('class'):
            if not div.has_attr('data-trans-id') and not _has_block_children(div) and div.get_text(strip=True):
                wrap_block(div)

    # 3. Catch orphaned text nodes (text directly inside body or a mixed div)
    for text_node in soup.find_all(string=True):
        if not text_node.strip():
            continue
            
        if isinstance(text_node, (Comment, Doctype)):
            continue
        
        parent = text_node.parent
        if parent and parent.name in ('style', 'script', 'head', 'title', 'meta'):
            continue
        
        # Walk up to see if it is inside a translation-row
        in_trans_block = False
        p = parent
        while p and p.name != 'body':
            if p.has_attr('data-trans-id'):
                in_trans_block = True
                break
            p = p.parent
            
        if not in_trans_block:
            # Wrap the orphaned text in a span, then wrap the span in a translation row
            span = soup.new_tag('span')
            text_node.wrap(span)
            wrap_block(span)

    return str(soup)

def extract_translation_blocks(html: str) -> list[dict]:
    """Extract a list of {"id": "...", "text": "..."} for translation."""
    soup = BeautifulSoup(html, 'html.parser')
    blocks = []
    for tag in soup.find_all(attrs={'data-trans-id': True}):
        orig = tag.find(class_='track-original')
        if orig:
            # Regular EPUB format
            inner_html = "".join(str(c) for c in orig.contents).strip()
            if inner_html:
                blocks.append({
                    "id": tag['data-trans-id'],
                    "html": inner_html
                })
        elif tag.parent and tag.parent.name == 'td':
            # Dante format: tag is <p data-trans-id="..."> directly inside a td
            parent_classes = tag.parent.get('class', [])
            if 'track-text' in parent_classes:
                inner_html = "".join(str(c) for c in tag.contents).strip()
                if inner_html:
                    blocks.append({
                        "id": tag['data-trans-id'],
                        "html": inner_html
                    })
    return blocks

def inject_translated_text(html: str, translations: dict[str, str]) -> str:
    """Replace inner HTML of data-trans-id elements with translated text."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(attrs={'data-trans-id': True}):
        tid = tag['data-trans-id']
        if tid in translations:
            trans_container = tag.find(class_='track-translation')
            if trans_container:
                # Regular EPUB format
                trans_html = translations[tid]
                trans_container.clear()
                trans_container.append(BeautifulSoup(trans_html, 'html.parser'))
            elif tag.parent and tag.parent.name == 'td':
                # Dante format
                tr = tag.find_parent('tr')
                if tr:
                    ai_td = tr.find('td', class_='track-ai_translation')
                    if not ai_td:
                        ai_td = soup.new_tag('td', attrs={'class': 'track-ai_translation'})
                        tr.append(ai_td)
                    
                    existing_p = ai_td.find('p', attrs={'data-trans-id': f"{tid}_ai"})
                    if not existing_p:
                        existing_p = soup.new_tag('p', attrs={'class': 'line', 'data-trans-id': f"{tid}_ai"})
                        ai_td.append(existing_p)
                    
                    existing_p.clear()
                    existing_p.append(BeautifulSoup(translations[tid], 'html.parser'))
    
    return str(soup)
