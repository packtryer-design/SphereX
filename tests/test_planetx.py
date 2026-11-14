import numpy as np
from api.imaging.planetx import found, plant, remove_static, search


def test_shift_and_stack_finds_a_planet_too_faint_for_any_frame() -> None:
    rng = np.random.default_rng(1)
    n, k = 41, 40
    dt = np.linspace(-1.5, 1.5, k)  # days
    zs = [rng.normal(0, 1, (n, n)) for _ in range(k)]
    zs = [
        z + np.where((np.mgrid[:n, :n][0] == 10) & (np.mgrid[:n, :n][1] == 30), 50, 0) for z in zs
    ]
    res = remove_static(zs, [1] * k)
    assert np.isnan(res[:, 10, 30]).all()  # the fixed bright star is masked out

    floor = search(res, dt)[0][0]  # pure noise: the false-alarm level
    x0, y0, vx, vy = 20.0, 20.0, 2.0, -1.0
    cands = search(plant(res, dt, x0, y0, vx, vy, 1.5), dt)  # 1.5 sigma: invisible per frame
    # found(): a candidate above the noise floor within 1.5 px and 2 grid steps of the truth
    assert found(cands, x0, y0, vx, vy, floor) is not None
    assert found(cands, 5.0, 35.0, vx, vy, floor) is None  # and nothing where none was planted
