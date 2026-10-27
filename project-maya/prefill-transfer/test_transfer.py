"""CPU-only guards for the actual compact reader extracted from the patch."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class TransferTests(unittest.TestCase):
    def test_compact_reader_against_independent_rows(self):
        patch = (Path(__file__).resolve().parent.parent /
                 'build-context/patch/v1.1.30-transfer/30-pr520-transfer.patch').read_text()
        added = '\n'.join(s[1:] for s in patch.splitlines() if s.startswith('+') and not s.startswith('+++'))
        functions = added[added.index('    bool read_mx_member('):added.index('    // copy_ahead')]
        # Only the two reader functions precede the next unrelated transfer hunk.
        end = functions.index('\n    }', functions.index('    void mx_down_member(')) + len('\n    }')
        functions = functions[:end]
        self.assertIn('std::memmove', functions)
        self.assertIn('mx_part_ptr', functions)
        source = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
namespace gg {
int expert_type(const auto&, int) { return 39; }
size_t type_row_bytes(int, int columns) { assert(columns % 32 == 0); return size_t(columns / 32) * 17; }
}
struct Layout { size_t trellis[3]; };
struct Layer { Layout lay, hlay; int ff0, ffn; std::vector<int> ram; };
struct Reader {
    struct { int dim, ff; } g;
    int NH;
    std::vector<Layer> members;
    std::vector<uint8_t> whole;
    std::array<std::vector<uint8_t>, 2> parts[3];
    const Layer& member(const Layer&, int m) const { return members[m]; }
    int mx_n(int r) const { return r == 2 ? g.dim : g.ff; }
    size_t mx_row_b(const Layer&, int r) const { return gg::type_row_bytes(39, r == 2 ? g.ff : g.dim); }
    const uint8_t* mx_part_ptr(const Layer&, int, int r, int x) const { return parts[r][x].data(); }
    bool read_mx_file(const Layer&, int, uint8_t* dst) const { memcpy(dst, whole.data(), whole.size()); return true; }
''' + functions + r'''
};
size_t aligned(size_t n) { return (n + 255) & ~size_t(255); }
Layout layout(int dim, int ff) {
    size_t gu = aligned(size_t(ff) * gg::type_row_bytes(39, dim));
    return Layout{{0, gu, 2 * gu}};
}
int main() {
    int cases = 0;
    for (int dim : {128, 5120}) for (int ff : {2304, 2368})
    for (int tp : {1, 2, 4, 8}) for (int numa : {1, 2}) for (int rotation : {0, 1}) {
        Reader r;
        r.g = {dim, ff}; r.NH = numa;
        Layer l{layout(dim, ff), layout(dim, ff), 0, ff, {0}};
        size_t bytes = l.lay.trellis[2] + aligned(size_t(dim) * gg::type_row_bytes(39, ff));
        r.whole.resize(bytes);
        uint32_t state = 1337;
        for (auto& b : r.whole) { state = state * 1664525u + 1013904223u; b = state >> 24; }
        for (int role = 0; role < 3; ++role) {
            const size_t n = size_t(r.mx_n(role) / numa) * r.mx_row_b(l, role);
            for (int x = 0; x < numa; ++x)
                r.parts[role][x].assign(r.whole.begin() + l.lay.trellis[role] + x * n,
                                        r.whole.begin() + l.lay.trellis[role] + (x + 1) * n);
        }
        int first = 0;
        for (int m = 0; m < tp; ++m) {
            const int blocks = ff / 32 / tp + (((m + rotation) % tp) < (ff / 32) % tp);
            r.members.push_back(Layer{l.lay, layout(dim, blocks * 32), first, blocks * 32, {}});
            first += blocks * 32;
        }
        assert(first == ff);
        for (int m = 0; m < tp; ++m) for (bool ram : {false, true}) {
            l.ram[0] = ram ? 0 : -1;
            const Layer& part = r.members[m];
            constexpr size_t guard = 256;
            std::vector<uint8_t> out(bytes + 2 * guard, 0xa5);
            assert(r.read_mx_member(l, 0, m, out.data() + guard));
            for (int role = 0; role < 3; ++role) {
                const size_t pitch = r.mx_row_b(l, role);
                const size_t width = role == 2 ? gg::type_row_bytes(39, part.ffn) : pitch;
                const int rows = role == 2 ? dim : part.ffn;
                const size_t col = role == 2 ? gg::type_row_bytes(39, part.ff0) : 0;
                const int row0 = role == 2 ? 0 : part.ff0;
                for (int row = 0; row < rows; ++row)
                    assert(memcmp(out.data() + guard + part.hlay.trellis[role] + row * width,
                                  r.whole.data() + l.lay.trellis[role] + (row0 + row) * pitch + col,
                                  width) == 0);
            }
            for (size_t i = 0; i < guard; ++i)
                assert(out[i] == 0xa5 && out[guard + bytes + i] == 0xa5);
            ++cases;
        }
    }
    std::cout << cases << " compact reader cases passed (TP1/2/4/8, NUMA1/2, RAM/file, rotations, guards)\n";
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, binary = Path(tmp) / 'reader.cpp', Path(tmp) / 'reader'
            cpp.write_text(source)
            subprocess.run(['g++', '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', str(cpp), '-o', str(binary)], check=True, timeout=60)
            proc = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=90,
                                  env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1'})
            self.assertRegex(proc.stdout, r'\d+ compact reader cases passed')
            print(proc.stdout.strip())


if __name__ == '__main__':
    unittest.main()
