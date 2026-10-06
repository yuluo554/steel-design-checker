"""确定性伪随机（splitmix64）。

口径 K8：禁用 stdlib `random`（其 Mersenne Twister 输出与解释器实现细节绑定，
跨版本不可保证），一律用本类的固定算法，保证同 seed 同序列、跨机器逐字节一致。
"""

_MASK = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15


class SplitMix64(object):
    def __init__(self, seed: int):
        self.state = seed & _MASK

    def next_u64(self) -> int:
        self.state = (self.state + _GOLDEN) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return (z ^ (z >> 31)) & _MASK

    def below(self, n: int) -> int:
        if n <= 0:
            raise ValueError("below() 需要正整数上界，收到 %r" % n)
        return self.next_u64() % n

    def pick(self, sequence):
        return sequence[self.below(len(sequence))]
