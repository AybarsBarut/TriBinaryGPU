# RadixLab — FAQ

## Is RGB a "three-valued" system? Does it relate to ternary logic?

No. RGB uses three channels (red, green, blue) because human colour vision has three cone types. This is a
**colour-encoding** choice. Each channel is still stored as an ordinary binary number (typically 8 bits).
A GPU that draws RGB images works the same on binary or ternary logic. Three colour channels say nothing
about the logic radix.

We still try one related workload: a **3-level pixel channel** (e.g. values {-1,0,+1} per channel). It is
treated as a workload with a golden reference, like any other. Its result is not evidence for or against
any radix claim beyond what it measures.

## Isn't quaternary just two bits?

Logically, yes. A base-4 digit carries exactly 2 bits. Radix economy is also the same: `4/ln 4 = 2/ln 2`
(`hypotheses.md`, H1). A quaternary design can differ from a binary one only through **multi-level
signalling**, where one wire or one storage cell holds four voltage levels (MLC-like). That brings
density benefits and noise-margin costs, which come in through the cell parameters, with a noise margin
of 1/6 of the swing instead of 1/2. GPU-Q results are only about that trade-off.

## "Drawing shapes is easier without binary" — is that tested?

Not as stated. Triangle and circle drawing rely on a sign test (which side of an edge) and on rounding.
Balanced ternary has cheap negation and round-to-nearest-by-truncation, but its sign is that of the
most significant *non-zero* trit, which needs more than reading one bit. Multiplications in the edge
function probably dominate the cost. We measure this: the share of cycles and energy spent in sign and
rounding operations, and the saving on those. See H3.

## Does ternary math help, or does ternary hardware help?

This is why GPU-BT exists. It runs balanced-ternary arithmetic on binary cells using 2 bits per trit.
Comparing GPU-B, GPU-BT and GPU-T separates the effect of the number system from the effect of the
hardware (`hypotheses.md` §0.2).

## Does ternary-weight neural inference need ternary hardware?

No. Weights in {-1,0,+1} remove multiplications on binary hardware too (conditional add or subtract).
H5 therefore compares ternary hardware against a **multiplier-free binary kernel**, and not only
against an INT8 multiply kernel.

## Are the numbers predictions about real chips?

No. All cell parameters are assumptions with stated sources and confidence. The study shows where an
architectural advantage exists, vanishes or reverses under a ±50% change of those assumptions. A
result that holds only in a subrange is labelled as such.

## What if ternary or quaternary performs worse?

Then that is the result, and it is reported as it is.

## Why not use the Rust/C++ choice that is faster to write?

See `docs/decisions/0001-core-language.md`.

## Is the AI (NVIDIA NIM) part of the simulation?

No. NIM is a language-model service used for drafts, review and test ideas. Everything it produces is
verified by the same equivalence tests as hand-written code, and numbers in AI-written text are never typed
by the model. All simulations run with no API key.
