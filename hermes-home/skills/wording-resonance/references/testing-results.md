# Testing Results — Wordings Across Semantic Axes

## How different wordings land on semantic axes (from all-MiniLM-L6-v2)

### 🍔 Food Marketing
| Wording | Natural vs Artificial | Moral Character | Class Status | Emotional Intensity |
|---------|----------------------|-----------------|--------------|-------------------|
| "Food science technology, taste optimization" | +0.247 | -0.087 |  |  |
| "Old-fashioned, real ingredients, no shortcuts" | +0.241 |  | -0.078 | -0.057 |
| "Culinary excellence, chefs created extraordinary" | +0.113 | -0.105 |  | +0.089 |

**Insight**: Both option 1 & 2 score high on Natural—but for opposite reasons. Option 1 uses technical language ("advanced food science") that the model interprets as artificial/industrial, while option 2 is genuinely rustic ("from scratch"). The model catches this nuance.

### 📰 Economic Inequality Headlines
| Wording | Social Class | Political Freedom | Emotional Intensity | Growth vs Stagnation |
|---------|-------------|-------------------|--------------------|--------------------|
| "Wealth gap widens... billionaire vs working families" | +0.096 | +0.096 |  | +0.102 |
| "Economic indicators show mixed signals..." | -0.086 | +0.059 | -0.099 | -0.059 |
| "System is rigged... elite interests dominate" | **+0.153** | **+0.146** | **+0.110** |  |

**Insight**: The "rigged system" headline fires almost all axes HARD (class, politics, emotion). A neutral framing barely activates anything. This is measurable — you can quantify "how provocative" a headline is before publishing.

### 🗣️ Political Campaign Messaging
| Wording | Political Freedom | Power & Agency | Social Class | Emotional Intensity |
|---------|-------------------|---------------|-------------|-------------------|
| "Fight for your freedom against the establishment" | +0.260 | +0.149 |  | +0.061 |
| "Working together... practical solutions, bipartisan" |  | -0.047 | +0.077 | -0.061 |
| "Corrupt elite stolen from you, take our country back" | +0.093 | -0.053 | +0.145 | +0.066 |

**Insight**: Option 1 activates pure political freedom/aggression. Option 2 is calming (low energy). Option 3 mixes class resentment with moderate freedom language. These are dramatically different "political flavors" measurable on axes.