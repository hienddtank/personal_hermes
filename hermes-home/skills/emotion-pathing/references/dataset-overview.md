# Dataset Reference: Text-to-Reaction Labels for Training

Datasets with labeled human emotional/psychological reactions to text. Useful for training a model that maps embedding projections to predicted reader responses.

## Primary Datasets

### GoEmotions (Google)
- **Size**: 58,009 Reddit comments from popular English subreddits
- **Labels**: 27 emotion categories + Neutral (multi-label)
- **Emotions**: admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, remorse, sadness, surprise
- **HuggingFace**: `datasets/google-research/goemotions`
- **Best for**: Training a classifier from embedding axis projections → emotion prediction
- **Limitation**: Reddit-specific voice; may not generalize to formal/blog writing

### Moral Foundations Reddit Corpus (MFT-NLP)
- **Size**: Large-scale Reddit corpus
- **Labels**: 5 Moral Foundations Theory dimensions — care/harm, fairness/cheating, loyalty/betrayal, authority/subversion, sanctity/degradation
- **URL**: `mft-nlp.com` → datasets page
- **Best for**: Training moral framing predictions; maps well to persuasion and emotional impact
- **Strength**: Captures the multi-moral dimensionality of emotional reactions

### Persuasion in Text (PIT) — SemEval 2019 Task 6
- **Type**: Persuasion technique detection (not direct reaction labels)
- **Techniques**: Appeal to emotion, bandwagon, name-calling, flag-waving, etc.
- **Best as**: Feature augmentation alongside axis projections — knowing which techniques are used helps predict reactions even without explicit emotion labels

### SemEval 2021 Task 6 (Persuasion in Memes)
- Extension of PIT to multimodal (text + image) persuasion technique detection
- Smaller dataset but useful for meme/social media emotional dynamics

## Training Pipeline Design

For a proper embedding→reaction engine:

1. **Input**: Text → embed → project onto semantic axes → get axis projection vector
2. **Label**: Human emotion/moral frame from GoEmotions or Moral Foundations corpus
3. **Model**: Regression/classifier mapping axis projections to emotion probabilities
4. **Output**: For any new text, predict which emotions readers will experience and their intensity

The axis projections serve as the feature space — much lower dimensional than raw embeddings, more interpretable, and directly tied to discovered semantic meaning.

## Dataset Gap

No existing dataset provides: *"for this exact wording variant, here's how real people reacted"* in a controlled A/B testing format. The **Behavior-in-the-wild Persuasiveness** (Anthropic/Stanford) dataset is closest — it measures actual persuasion outcomes of tested variants — but focuses on persuasion success rather than specific emotional reactions.
