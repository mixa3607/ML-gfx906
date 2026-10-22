// Exercise both logical warps with DIFFERENT ballots: a 32-thread probe misses
// accidental reuse of the low half of a wave64 ballot.
#include <hip/hip_runtime.h>
#include <cstdio>

#define CHECK(call) do { auto e = (call); if (e != hipSuccess) { \
    std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(e)); return 1; } } while (0)

__global__ void probe(unsigned* result) {
    const unsigned tid = threadIdx.x;
    const unsigned lane = tid & 31;
    const unsigned warp = tid / 32;
    const unsigned ballot = __ballot_sync(0xffffffffu, (lane & 1) == (warp & 1));
    const unsigned first = __shfl_sync(0xffffffffu, tid, 0);
    const unsigned other = __shfl_xor_sync(0xffffffffu, tid, 1);
    __shared__ unsigned exchange[128];
    exchange[tid] = tid;
    __syncwarp();
    result[tid] = ballot == ((warp & 1) ? 0xaaaaaaaau : 0x55555555u)
        && first == warp * 32 && other == (tid ^ 1)
        && exchange[tid ^ 1] == (tid ^ 1);
}

int main() {
    hipDeviceProp_t p{};
    CHECK(hipGetDeviceProperties(&p, 0));
    std::printf("wave64 half-warps: %s (%s), wave%d\n", p.name, p.gcnArchName, p.warpSize);
    if (p.warpSize != 64) return 1;
    unsigned* device = nullptr;
    CHECK(hipMalloc(&device, 128 * sizeof(unsigned)));
    probe<<<1, 128>>>(device);
    CHECK(hipGetLastError());
    unsigned result[128]{};
    CHECK(hipMemcpy(result, device, sizeof(result), hipMemcpyDeviceToHost));
    CHECK(hipFree(device));
    for (unsigned i = 0; i < 128; ++i) {
        if (!result[i]) { std::fprintf(stderr, "half-warp parity failed at thread %u\n", i); return 1; }
    }
    std::puts("wave64 half-warps: PASS (4 logical warps, ballot/shuffle/shared-memory sync)");
}
