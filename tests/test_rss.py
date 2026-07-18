import unittest
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from hn_briefing import Article, Comment, Story, StoryBrief
from hn_briefing_rss import render_rss


class RSSRenderingTests(unittest.TestCase):
    def test_render_rss_outputs_parseable_rss_20_feed(self):
        story = Story(
            id=123,
            rank=1,
            title="Example GPU Database Launch",
            url="https://example.com/story",
            hn_url="https://news.ycombinator.com/item?id=123",
            site="example.com",
            points=42,
            author="alice",
            age="1 hour ago",
            comment_count=7,
        )
        brief = StoryBrief(
            story=story,
            article=Article(url=story.url, fetched=True, text=""),
            comments=[Comment(author="reader", text="Looks useful.")],
            article_summary="The article describes a GPU-backed database launch.",
            discussion_summary="HN discussion highlights: early developer interest.",
        )

        xml = render_rss(
            [brief],
            generated_at=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
        )
        root = ET.fromstring(xml)
        channel = root.find("channel")
        item = channel.find("item")

        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.attrib["version"], "2.0")
        self.assertEqual(channel.findtext("title"), "Hacker News Front-Page Briefing")
        self.assertEqual(channel.findtext("link"), "https://news.ycombinator.com/news")
        self.assertEqual(item.findtext("title"), "Example GPU Database Launch")
        self.assertEqual(item.findtext("link"), "https://example.com/story")
        self.assertIn("<![CDATA[", xml)
        self.assertIn("1 hour ago - example.com - 7 HN comments", item.findtext("description"))
        self.assertIn("<p>Article Summary:</p>", item.findtext("description"))
        self.assertIn("GPU-backed database", item.findtext("description"))
        self.assertIn("<p>early developer interest.</p>", item.findtext("description"))
        self.assertNotIn("HN discussion highlights:", item.findtext("description"))
        self.assertIn('<a href="https://example.com/story">Article</a>', item.findtext("description"))
        self.assertIsNone(item.find("guid"))


if __name__ == "__main__":
    unittest.main()
