# ReCombinator

ReCombinator creates a concise Markdown briefing from the Hacker News front page.
It scrapes the ranked stories from `news.ycombinator.com`, fetches the linked
articles when possible, samples HN discussion, and produces a brief overview with
click-through links.

The first implementation uses only Python's standard library. That keeps the
project easy to run in locked-down environments and makes the scraping logic
plain to inspect.

## Single-Script Quick Start

Run the self-contained script and pass the Markdown destination as the first
argument:

```powershell
python hn_briefing.py C:\path\to\briefing.md
```

Useful options:

```powershell
python hn_briefing.py C:\path\to\briefing.md --limit 10 --comments 8 --article-chars 12000
```

The script creates parent directories for the output path when needed.

## RSS Output

To create a publishable RSS 2.0 XML feed instead of Markdown, run:

```powershell
python hn_briefing_rss.py C:\path\to\hn-briefing.xml
```

The RSS script writes an `<rss version="2.0">` document with a channel and one
item per HN story. Each item includes the story title, article link, summary,
HN discussion link, GUID, comments URL, and metadata when available.

## Package Quick Start

```powershell
python -m recombinator --limit 10 --output briefing.md
```

If `python` is not on your PATH, use any Python 3.11+ interpreter:

```powershell
C:\path\to\python.exe -m recombinator --limit 10 --output briefing.md
```

## What It Collects

- The top ranked items from the Hacker News front page.
- Story title, source URL, Hacker News discussion URL, rank, points, author,
  age, and comment count when available.
- Readable text from each linked article page.
- Top-level discussion snippets from the corresponding HN item page.

## Output

The CLI writes Markdown by default:

```powershell
python -m recombinator --limit 10
```

Useful options:

- `--limit`: number of front-page stories to include.
- `--comments`: maximum HN comments to sample per story.
- `--article-chars`: maximum readable article characters to retain per story.
- `--timeout`: HTTP timeout in seconds.
- `--output`: write Markdown to a file instead of stdout.

## Notes

HN includes posts that are not external articles, such as Ask HN, Show HN, and
jobs. ReCombinator still includes them, but article extraction may be sparse and
the discussion summary will carry more of the briefing.
