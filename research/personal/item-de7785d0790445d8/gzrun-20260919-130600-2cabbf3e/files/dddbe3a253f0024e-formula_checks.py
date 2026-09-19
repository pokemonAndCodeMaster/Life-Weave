"""CPU arithmetic checks; no model, weights, or driving data. Run with stdlib Python."""
import math,json,pathlib,statistics

def score(F): return math.log10(math.log(.5)/math.log1p(-F))
rows=[]
for z in [0,-1,-2,-3,1]:
 F=.5*math.erfc(-z/math.sqrt(2))
 rows.append(dict(z=z,spacing=20*math.exp(.5*z),F=F,M=score(F),n=10**score(F)))
# Eq15: piecewise-linear TPR at FPR 0,.1,.3,1: 0,.8,.9,1.
# FPR as a function of recall on [.8,.9] and [.9,1].
A=(.1*(.9+.7)/2+.1*(.7+0)/2)/.2
# Equivalent horizontal integration above y=.8.
A_horizontal=((.3-.1)*(.0+.1)/2+(1-.3)*(.1+.2)/2)/.2
# Old equation integrates ordinary TPR over FPR .8..1.
y08=.9+(.8-.3)/(.7)*.1
A_old=.2*(y08+1)/2/.2
# In v5 text q^n>.5 means n < log(.5)/log(q).
q=.99;nstar=math.log(.5)/math.log(q)
# Strict JS bound: two distributions always JS <= ln2. Code proxy for
# N(-2,1) and N(2,1) has 1/2*(KL to N(0,1)+KL to N(0,1)) = 2.
proxy_js=2.0
r={'kind':'toy arithmetic, not paper replication','lognormal_example':rows,
 'eq15':{'vertical_exact':A,'horizontal_exact':A_horizontal,'v3_formula_same_curve':A_old},
 'inequality':{'q':q,'nstar':nstar,'q_power_10':q**10,'q_power_100':q**100},
 'clipping':{'eps':1e-6,'score_upper_float64':math.log10(math.log(.5)/math.log(1-1e-6)),'score_lower':0},
 'js_proxy':{'normal_means':[-2,2],'variances':[1,1],'code_proxy':proxy_js,'strict_JS_upper_bound':math.log(2)},
 'selection_percent':{'reconstructed_of_original':6664/8895*100,'filtered_of_original':4875/8895*100,'voted_of_original':2591/8895*100,'voted_of_filtered':2591/4875*100},
 'sample_sum':sum([1787,611,93,29,31]),'test_positive_fraction':2591/(2591+3777)}
assert math.isclose(A,A_horizontal) and math.isclose(A,.575)
assert q**10>.5 and 10<nstar and q**100<.5 and 100>nstar
assert proxy_js>math.log(2)
p=pathlib.Path(__file__).with_name('formula-results.json');p.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
