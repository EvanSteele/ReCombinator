import unittest

from recombinator.article import extract_article
from hn_briefing import extract_article as extract_script_article


ARTICLE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Important Compiler Release</title>
    <script>window.noisy = true;</script>
  </head>
  <body>
    <nav>Home Products Pricing Sign in</nav>
    <main>
      <h1>Important Compiler Release</h1>
      <p>Share Facebook LinkedIn Mail Copy link</p>
      <p>The compiler team’s new version has faster incremental builds and lower memory use.</p>
      <p>Developers working on large codebases should see shorter feedback loops during local testing.</p>
    </main>
    <footer>Privacy Policy</footer>
  </body>
</html>
"""

REDDIT_HTML = """
<!doctype html>
<html>
  <head>
    <title>After OpenAI's CDC proof announcement, GPT-5.6 used a similar prompt to close a 30-year gap in convex optimization, verified in Lean : math</title>
  </head>
  <body>
    <div class="sr-bar">AskReddit DIY OldSchoolCool TwoXChromosomes Music</div>
    <form>Want to join? Log in</form>
    <div class="side">
      Submit a new link Submit a new text post MODERATORS Welcome to Reddit,
      Become a Redditor and join one of thousands of communities.
      <div class="usertext-body">
        Welcome to This subreddit is for discussion of mathematics.
        Rule 1: Stay on-topic.
      </div>
    </div>
    <div class="thing link">
      <span>715</span><span>717</span>
      <a class="title" href="https://example.com/proof">
        After OpenAI's CDC proof announcement, GPT-5.6 used a similar prompt
        to close a 30-year gap in convex optimization, verified in Lean
      </a>
      <p>2 days ago 169 comments Want to add to the discussion?</p>
    </div>
    <div class="commentarea">
      <div class="usertext-body">This comment should not be article text.</div>
    </div>
    <footer>
      Advertise - technology Rendered by PID 463075 on reddit-service-r2-loggedout
      at 2026-07-18 16:51:41.465162+00:00 running 1bce727 country code: US.
    </footer>
  </body>
</html>
"""


class ArticleExtractionTests(unittest.TestCase):
    def test_extracts_readable_article_text(self):
        article = extract_article("https://example.com", ARTICLE_HTML, "text/html")

        self.assertEqual(article.title, "Important Compiler Release")
        self.assertIn("team's new version", article.text)
        self.assertIn("faster incremental builds", article.text)
        self.assertIn("shorter feedback loops", article.text)
        self.assertNotIn("window.noisy", article.text)
        self.assertNotIn("Privacy Policy", article.text)
        self.assertNotIn("Share Facebook", article.text)

    def test_reddit_pages_extract_submission_not_chrome(self):
        article = extract_article(
            "https://old.reddit.com/r/math/comments/1uxj3cy/example/",
            REDDIT_HTML,
            "text/html",
        )

        self.assertIn("30-year gap in convex optimization", article.text)
        self.assertNotIn("Want to add to the discussion", article.text)
        self.assertNotIn("Rendered by PID", article.text)
        self.assertNotIn("Submit a new link", article.text)
        self.assertNotIn("Rule 1: Stay on-topic", article.text)
        self.assertNotIn("This comment should not be article text", article.text)

    def test_single_script_reddit_extraction_matches_package_filtering(self):
        article = extract_script_article(
            "https://old.reddit.com/r/math/comments/1uxj3cy/example/",
            REDDIT_HTML,
            "text/html",
        )

        self.assertIn("30-year gap in convex optimization", article.text)
        self.assertNotIn("Want to add to the discussion", article.text)
        self.assertNotIn("Rendered by PID", article.text)


if __name__ == "__main__":
    unittest.main()
