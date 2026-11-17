import gzip
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.datasets import download_file, iterative_core, preprocess_gowalla
from ml.poi_model import POIGraph, dataset_fingerprints, load_data, model_metrics, seen_items, temporal_split


class DatasetTests(unittest.TestCase):
    def test_download_checksum_cache_and_corrupt_cache_recovery(self):
        payload = b"verified public dataset\n"
        checksum = hashlib.sha256(payload).hexdigest()
        hits = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(1)
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'data.csv'
                url = f'http://127.0.0.1:{server.server_port}/data.csv'
                download_file(url, path, checksum)
                download_file(url, path, checksum)
                self.assertEqual(len(hits), 1)
                path.write_bytes(b'corrupt')
                download_file(url, path, checksum)
                self.assertEqual(len(hits), 2)
                self.assertEqual(path.read_bytes(), payload)
                path.with_suffix('.csv.download.json').write_text('interrupted receipt')
                download_file(url, path, checksum)
                self.assertEqual(len(hits), 2)
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    download_file(url, path, '0' * 64, retries=1)
                self.assertFalse(path.with_suffix('.csv.part').exists())
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_gowalla_real_schema_time_units_missing_categories_and_subset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'gowalla.txt.gz'
            records = []
            for user in (10, 20, 30):
                for item in range(6):
                    date = pd.Timestamp('2010-01-04T23:30:00Z') + pd.Timedelta(days=item, minutes=user)
                    records.append(f'{user}\t{date.isoformat()}\t10.0\t30.0\t{100+item}')
            records.append(records[0])
            records.append('10\t2010-01-04T23:30:00Z\t999\t30\t999')
            with gzip.open(raw, 'wt', encoding='utf-8') as stream:
                stream.write('\n'.join(records) + '\n')
            prepared = preprocess_gowalla(raw, root/'processed', min_user_pois=2, min_poi_users=2)
            meta = json.loads((prepared/'experiment_metadata.json').read_text())
            self.assertFalse(meta['has_categories'])
            self.assertEqual(meta['invalid_events_removed'], 1)
            self.assertEqual(meta['duplicate_events_removed'], 1)
            pois, events, user_ids, poi_ids, _ = load_data(prepared)
            self.assertEqual(len(events), 18)
            self.assertEqual(set(pois.category), {'unknown'})
            first = events.iloc[0]
            self.assertEqual(int(first.ts), int(pd.Timestamp('2010-01-04T23:40:00Z').timestamp()))
            self.assertEqual(int(first.hour), 1)  # UTC + 2 crosses midnight.
            self.assertEqual(int(first.day_of_week), 1)  # Tuesday, Monday=0.
            train, validation, test = temporal_split(events)
            model = POIGraph(len(user_ids), pois[['lat','lon']].to_numpy(), np.zeros(len(pois),dtype=int),
                             dim=8, layers=1, category_features=False)
            model.build_graph(train[['user','item']].to_numpy())
            metrics = model_metrics(model, test, seen_items(train), batch_size=2)
            self.assertEqual(metrics['events'], len(test))
            subset = preprocess_gowalla(raw, root/'subset', max_users=2, seed=42, min_user_pois=2, min_poi_users=2)
            repeated = preprocess_gowalla(raw, root/'repeat', max_users=2, seed=42, min_user_pois=2, min_poi_users=2)
            self.assertEqual((subset/'checkins.csv').read_bytes(), (repeated/'checkins.csv').read_bytes())
            self.assertTrue(json.loads((subset/'experiment_metadata.json').read_text())['is_subset'])

    def test_iterative_core_reaches_fixed_point(self):
        events = pd.DataFrame({'u':[0,0,1,1,2], 'l':[0,1,0,1,2]})
        result = iterative_core(events,2,2)
        self.assertEqual(len(result),4)
        self.assertTrue((result.groupby('u').l.nunique()>=2).all())
        self.assertTrue((result.groupby('l').u.nunique()>=2).all())

    def test_batch_scores_match_pair_scores_with_or_without_categories(self):
        torch.manual_seed(42)
        for categories in (True, False):
            model = POIGraph(2, [[16,108],[16.1,108.1],[16.2,108.2]], [0,1,2], dim=8, layers=1, category_features=categories)
            model.build_graph([[0,0],[0,1],[1,2]])
            users=torch.tensor([0,1]); hours=torch.tensor([8,18]); weekdays=torch.tensor([1,5])
            times=torch.tensor([1680000000.,1680000123.],dtype=torch.float64)
            emb=model.embeddings()
            batched=model.scores_batch(users,hours,weekdays,times,emb)
            for row in range(2):
                for item in range(3):
                    score=model.score_pairs(users[row:row+1],torch.tensor([item]),hours[row:row+1],weekdays[row:row+1],times[row:row+1],emb)
                    self.assertTrue(torch.allclose(score[0],batched[row,item],atol=1e-5))

    def test_newline_aliases_match_windows_and_github_csv_without_accepting_other_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for variant, ending in [('lf',b'\n'),('crlf',b'\r\n')]:
                path=root/variant;path.mkdir()
                for name in ['danang_pois_full.csv','danang_checkins_full.csv']:
                    (path/name).write_bytes(ending.join([b'header',b'value',b'']))
            raw_lf,aliases_lf=dataset_fingerprints(root/'lf')
            raw_crlf,aliases_crlf=dataset_fingerprints(root/'crlf')
            self.assertNotEqual(raw_lf,raw_crlf)
            self.assertEqual(aliases_lf,aliases_crlf)
            self.assertIn(raw_lf,aliases_crlf)
            self.assertIn(raw_crlf,aliases_lf)
            (root/'lf/danang_pois_full.csv').write_bytes(b'changed\n')
            self.assertNotEqual(aliases_lf,dataset_fingerprints(root/'lf')[1])

    def test_heavily_tied_users_still_have_three_nonoverlapping_splits(self):
        frame=pd.DataFrame({'user':[0]*10,'ts':[1]*8+[2,3]})
        train,validation,test=temporal_split(frame)
        self.assertEqual([len(train),len(validation),len(test)],[8,1,1])


if __name__ == '__main__':
    unittest.main()
