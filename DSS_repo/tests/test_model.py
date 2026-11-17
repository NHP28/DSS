import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.poi_model import (POIGraph, evaluate, negative_samples, restore_bundle,
                          seed_everything, temporal_split)


class ModelTests(unittest.TestCase):
    def setUp(self):
        seed_everything(42)
        torch.set_num_threads(2)
        self.coords = np.array([[16.0,108.0],[16.1,108.1],[16.2,108.2]], np.float32)
        self.model = POIGraph(2, self.coords, [0,1,2], dim=8, layers=1)
        self.pairs = torch.tensor([[0,0],[0,1],[1,2]])
        self.model.build_graph(self.pairs)

    def test_negatives_never_positive_and_full_user_fails(self):
        seen = {0:{0,1},1:{1,2}}
        users = np.array([0,1]*100)
        values = negative_samples(users,seen,3,np.random.default_rng(1))
        self.assertTrue(all(n not in seen[u] for u,n in zip(users,values)))
        with self.assertRaises(ValueError): negative_samples([0],{0:{0,1,2}},3,np.random.default_rng(0))

    def test_binary_graph_and_scoring_consistency(self):
        original = self.model.adj.to_dense().clone()
        self.model.build_graph(torch.cat([self.pairs,self.pairs]))
        self.assertTrue(torch.equal(original,self.model.adj.to_dense()))
        emb = self.model.embeddings()
        vector = self.model.scores(0,8,1,1680000001.,emb)
        for item in range(3):
            score = self.model.score_pairs(torch.tensor([0]),torch.tensor([item]),torch.tensor([8]),
                                          torch.tensor([1]),torch.tensor([1680000001.],dtype=torch.float64),emb)
            self.assertTrue(torch.allclose(score[0],vector[item],atol=1e-5))
        loss=self.model.loss(torch.tensor([0,1]),torch.tensor([0,2]),torch.tensor([2,0]),
                             torch.tensor([8,19]),torch.tensor([1,4]),torch.tensor([1680000001.,1680000002.],dtype=torch.float64))
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(self.model.time_category.weight.grad.abs().sum().item(),0)

    def test_artifact_roundtrip_restores_graph_mapping_and_predictions(self):
        bundle={"format_version":1,"model_config":{"n_users":2,"dim":8,"layers":1,"temporal":True,"spatial":True},
                "state_dict":self.model.state_dict(),"fit_pairs":self.pairs,"user_ids":[12,99],"poi_ids":[3,7,21]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.pt';torch.save(bundle,path)
            restored,meta=restore_bundle(path)
            self.assertEqual(meta['poi_ids'],[3,7,21])
            self.assertTrue(torch.allclose(self.model.scores(0,8,1,1680000001.),restored.scores(0,8,1,1680000001.)))

    def test_temporal_split_ties_stay_together(self):
        frame=pd.DataFrame({'user':[0]*10+[1]*10,'ts':[1,2,3,4,5,6,7,7,9,10]*2})
        train,val,test=temporal_split(frame)
        self.assertEqual(len(train)+len(val)+len(test),len(frame))
        for user in (0,1):
            self.assertLess(train[train.user==user].ts.max(),val[val.user==user].ts.min())
            self.assertLess(val[val.user==user].ts.max(),test[test.user==user].ts.min())

    def test_event_metrics_mask_seen_and_have_explicit_denominator(self):
        held=pd.DataFrame({'user':[0,0,0],'item':[0,1,2],'hour':[8]*3,'day_of_week':[0]*3,'ts':[1,2,3]})
        result=evaluate(lambda row:np.array([100,5,4]),held,{0:{0}},ks=(1,2,10))
        self.assertEqual(result['events'],2)
        self.assertEqual(result['excluded_seen_events'],1)
        self.assertEqual(result['HR@1'],.5)
        self.assertEqual(result['HR@2'],1)
        self.assertAlmostEqual(result['NDCG@2'],(1+1/np.log2(3))/2)


if __name__ == '__main__': unittest.main()
