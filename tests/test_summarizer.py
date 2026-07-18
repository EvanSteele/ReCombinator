import unittest

from recombinator.models import Article, Comment, Story
from recombinator.summarizer import brief_story


class SummarizerTests(unittest.TestCase):
    def test_brief_story_includes_article_and_discussion_summaries(self):
        story = Story(
            id=1,
            rank=1,
            title="GPU Database Startup Releases Open Source Engine",
            url="https://example.com",
            hn_url="https://news.ycombinator.com/item?id=1",
        )
        article = Article(
            url=story.url,
            fetched=True,
            text=(
                "Share Facebook LinkedIn Mail Copy link The startup released a teaser "
                "before the article body. "
                "The startup released an open source database engine that uses GPU memory "
                "to speed analytical queries for developer teams. "
                "The company says the release focuses on local deployment, predictable costs, "
                "and compatibility with existing data tools."
            ),
        )
        comments = [
            Comment(
                author="reader",
                age="5 minutes ago",
                text=(
                    "HN readers are debating whether GPU memory pricing makes this practical "
                    "for small engineering teams."
                ),
            )
        ]

        brief = brief_story(story, article, comments)

        self.assertIn("database engine", brief.article_summary)
        self.assertNotIn("Share Facebook", brief.article_summary)
        self.assertIn("HN discussion highlights", brief.discussion_summary)


if __name__ == "__main__":
    unittest.main()
