import unittest

from recombinator.hn import parse_comments, parse_front_page


FRONT_PAGE_HTML = """
<html><body>
<table>
  <tr class='athing submission' id='123'>
    <td align='right' class='title'><span class='rank'>1.</span></td>
    <td class='votelinks'><a href='vote?id=123&amp;how=up'>vote</a></td>
    <td class='title'>
      <span class='titleline'>
        <a href='https://example.com/post'>Example Launch Uses GPUs</a>
        <span class='sitebit comhead'> (<a href='from?site=example.com'><span class='sitestr'>example.com</span></a>)</span>
      </span>
    </td>
  </tr>
  <tr>
    <td colspan='2'></td>
    <td class='subtext'>
      <span class='score' id='score_123'>42 points</span>
      by <a href='user?id=alice' class='hnuser'>alice</a>
      <span class='age'><a href='item?id=123'>2 hours ago</a></span>
      | <a href='hide?id=123'>hide</a>
      | <a href='item?id=123'>14 comments</a>
    </td>
  </tr>
  <tr class='athing submission' id='456'>
    <td class='title'><span class='rank'>2.</span></td>
    <td class='votelinks'></td>
    <td class='title'><span class='titleline'><a href='item?id=456'>Ask HN: What changed?</a></span></td>
  </tr>
  <tr>
    <td colspan='2'></td>
    <td class='subtext'>
      <span class='score' id='score_456'>3 points</span>
      by <a href='user?id=bob' class='hnuser'>bob</a>
      <span class='age'><a href='item?id=456'>15 minutes ago</a></span>
      | <a href='hide?id=456'>hide</a>
      | <a href='item?id=456'>discuss</a>
    </td>
  </tr>
</table>
</body></html>
"""


COMMENTS_HTML = """
<html><body>
<tr class='athing comtr' id='900'>
  <td class='ind'></td>
  <td class='default'>
    <span class='comhead'><a href='user?id=carol' class='hnuser'>carol</a>
      <span class='age'><a href='item?id=900'>1 hour ago</a></span>
    </span>
    <div class='comment'><span class='commtext c00'>This release matters because it changes the cost profile for small teams.</span></div>
  </td>
</tr>
<tr class='athing comtr' id='901'>
  <td class='ind'></td>
  <td class='default'>
    <span class='comhead'><a href='user?id=dave' class='hnuser'>dave</a>
      <span class='age'><a href='item?id=901'>34 minutes ago</a></span>
    </span>
    <div class='comment'><div class='commtext c00'>The technical detail is interesting.<p>People are comparing it to older systems.</div></div>
  </td>
</tr>
</body></html>
"""


class HNParserTests(unittest.TestCase):
    def test_front_page_extracts_ranked_stories_and_metadata(self):
        stories = parse_front_page(FRONT_PAGE_HTML)

        self.assertEqual(len(stories), 2)
        self.assertEqual(stories[0].id, 123)
        self.assertEqual(stories[0].rank, 1)
        self.assertEqual(stories[0].title, "Example Launch Uses GPUs")
        self.assertEqual(stories[0].url, "https://example.com/post")
        self.assertEqual(stories[0].hn_url, "https://news.ycombinator.com/item?id=123")
        self.assertEqual(stories[0].site, "example.com")
        self.assertEqual(stories[0].points, 42)
        self.assertEqual(stories[0].author, "alice")
        self.assertEqual(stories[0].age, "2 hours ago")
        self.assertEqual(stories[0].comment_count, 14)

    def test_front_page_handles_hn_self_posts(self):
        story = parse_front_page(FRONT_PAGE_HTML)[1]

        self.assertEqual(story.url, "https://news.ycombinator.com/item?id=456")
        self.assertEqual(story.comment_count, 0)

    def test_comments_extract_text_author_and_age(self):
        comments = parse_comments(COMMENTS_HTML)

        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0].author, "carol")
        self.assertEqual(comments[0].age, "1 hour ago")
        self.assertIn("cost profile", comments[0].text)
        self.assertIn("older systems", comments[1].text)


if __name__ == "__main__":
    unittest.main()
