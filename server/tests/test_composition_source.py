import unittest
from unittest.mock import MagicMock, Mock, patch
import psycopg2
from app.utils.composition_source import composition_source_rows, CompositionSourceError


def connection(pages, invalid=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = invalid
    cursor.fetchall.side_effect = pages
    return conn, cursor


def row(branch, item):
    return {'branch_id': branch, 'item_definition_id': item}


class SourceTests(unittest.TestCase):
    def test_disconnect_resumes_after_last_page_without_duplicates(self):
        a, ca = connection([[row(1, 1), row(1, 2)], psycopg2.OperationalError('SSL closed')])
        b, cb = connection([[row(2, 1)], []])
        connect = Mock(side_effect=[a, b])
        progress = Mock()
        with patch('app.utils.composition_source.time.sleep'):
            result = list(composition_source_rows(connect, 2, progress))
        self.assertEqual(result, [row(1, 1), row(1, 2), row(2, 1)])
        query = cb.execute.call_args_list[1]
        self.assertIn('WHERE (branch_id, item_definition_id) > (%s, %s)', query.args[0])
        self.assertEqual(query.args[1], (1, 2, 2))
        a.close.assert_called_once()
        b.close.assert_called_once()
        progress.assert_called_once()

    def test_invalid_keys_fail_before_fetch(self):
        c, cur = connection([], invalid=row(1, 1))
        with self.assertRaises(CompositionSourceError):
            list(composition_source_rows(lambda: c))
        cur.fetchall.assert_not_called()
        c.close.assert_called_once()

    def test_failures_bounded(self):
        connect = Mock(side_effect=psycopg2.OperationalError('closed'))
        with patch('app.utils.composition_source.time.sleep'), self.assertRaises(CompositionSourceError):
            list(composition_source_rows(connect, max_attempts=3))
        self.assertEqual(connect.call_count, 3)

    def test_duplicate_page_rejected_before_yield(self):
        c, cur = connection([[row(1, 1), row(1, 1)]])
        with self.assertRaises(CompositionSourceError):
            next(composition_source_rows(lambda: c, 2))

    def test_consumer_failure_closes_connection(self):
        c, cur = connection([[row(1, 1), row(1, 2)]])
        stream = composition_source_rows(lambda: c, 2)
        next(stream)
        stream.close()
        c.close.assert_called_once()
