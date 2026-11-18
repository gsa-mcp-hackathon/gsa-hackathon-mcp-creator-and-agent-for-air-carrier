"""Intelligence analyst: infer missing line-of-accounting facts as scored leads.

Modules: loa (vocabulary), engine (candidates, features, scoring), learn
(labels, refit, calibration), backtest, residual (File C vs FPDS gaps),
sources (Spark loader). Output is always grade LEAD (D16).
"""
