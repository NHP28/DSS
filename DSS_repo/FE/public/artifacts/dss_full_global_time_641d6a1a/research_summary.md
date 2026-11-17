# Báo cáo lượt chạy POI



Run mode: full; protocol: global_time; seeds: [42, 123, 2026]





## danang

Novel event HR@10 mean: {'bpr_mf': 0.12515002727768684, 'geo_hourly': 0.10703764320785597, 'hourly_popularity': 0.08772504091653027, 'lightgcn': 0.11412984178941625, 'popularity': 0.050409165302782326, 'tas_gnn': 0.16661211129296236, 'tas_no_category': 0.15941080196399346, 'tas_no_space': 0.11456628477905073, 'tas_no_time': 0.12744135297326786}

Repeated test events excluded from novel metric: 21.32%.

Cold-user test events excluded: 3359.

Paired user CI (macro-user HR@10, exploratory comparisons):

reference,users,macro_user_HR10_difference,ci95_low,ci95_high,resamples
bpr_mf,524,0.041778894522215136,0.031134904310596102,0.05312881366495392,2000
geo_hourly,524,0.06250600497765967,0.04885332717095599,0.0757003043767048,2000
hourly_popularity,524,0.08266554751315641,0.06878198199524535,0.09677118063182555,2000
lightgcn,524,0.051483429165007526,0.0399548155245983,0.06259381005834334,2000
popularity,524,0.12045339050138107,0.10585199700784008,0.13512639441137697,2000
tas_no_category,524,0.007409791662710387,0.0009857627461887684,0.013922928299892822,2000
tas_no_space,524,0.05411103639662238,0.04292454857691163,0.06510514422847435,2000
tas_no_time,524,0.039790261585277306,0.029508054882718106,0.04948031257282773,2000


hotel: 295 catalog POIs, zero interactions; recommendation quality is unverified.

Synthetic interactions/ratings/prices/popularity; results cannot establish real user preference quality.

District labels contain spelling/prefix variants; raw values are reported without silently editing the source.

Catalog lacks per-row OSM element IDs; source attribution cannot be verified POI by POI from this CSV alone.



## gowalla

Novel event HR@10 mean: {'bpr_mf': 0.054836140526828114, 'geo_hourly': 0.056429013893395476, 'hourly_popularity': 0.02356862629420961, 'lightgcn': 0.05496396369821933, 'popularity': 0.023996342290787884, 'tas_gnn': 0.05321622764323569, 'tas_no_space': 0.055204861213533525, 'tas_no_time': 0.051389831175088246}

Repeated test events excluded from novel metric: 34.68%.

Cold-user test events excluded: 48010.

Paired user CI (macro-user HR@10, exploratory comparisons):

reference,users,macro_user_HR10_difference,ci95_low,ci95_high,resamples
bpr_mf,11419,-0.0027979360787028706,-0.004467606506888499,-0.001152218434750031,2000
geo_hourly,11419,-0.0027510141822952956,-0.0054833799164742455,-3.5314121514364944e-05,2000
hourly_popularity,11419,0.04123203147676057,0.038887971623308745,0.043546623632711744,2000
lightgcn,11419,-0.0009683119838737336,-0.0025314005845946006,0.0006072869183872806,2000
popularity,11419,0.03949210847531175,0.03707893915218727,0.04191667686479229,2000
tas_no_space,11419,-0.0007047028012355457,-0.0019344891644195686,0.000548685138777835,2000
tas_no_time,11419,0.002840661393889589,0.0015247246665739656,0.004159105854643247,2000


Local time approximated by longitude; timezone boundaries and DST are not modeled.

Activity core excludes many rare users/POIs; this is not a cold-start benchmark.

Movement diagnostics found implausible-speed or simultaneous-location steps; flags use static catalog coordinates and are not automatic deletion rules.



## Giới hạn chung

Catalog/eligibility/core transductive; lịch sử fit cố định trong test.

DIM/LAYERS cố định; tuning chỉ trong grid learning rate và epoch đã khai báo.

Seed std và user bootstrap phản ánh hai nguồn bất định khác nhau; không phải bằng chứng nhân quả.

Chưa kiểm chứng cold-start user, A/B test hoặc hiệu quả DSS trong notebook này.