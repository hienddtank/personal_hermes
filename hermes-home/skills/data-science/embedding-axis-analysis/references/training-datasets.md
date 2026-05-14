# Training Datasets: Text → Human Reaction Labels

Datasets that map text to measurable human responses — useful for training a model that predicts human reactions from embedding axis projections.

## GoEmotions (Google)
- **Size**: 58,099 Reddit comments
- **Labels**: 27 emotion categories + neutral (multi-label)
  - admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, remorse, sadness, surprise, sorrow
- **Source**: Popular English-language subreddits
- **Split**: Pre-defined train/val/test with inter-rater agreement filter (~25k samples)
- **URL**: `datasets/google-research/goemotions` on HuggingFace
- **Use case**: Direct mapping of text→emotion profile. Project texts onto axes, then train a classifier/regressor to predict which emotions readers will feel.

## Moral Foundations Reddit Corpus
- **Labels**: 5 moral foundations (care/harm, fairness/cheating, loyalty/betrayal, authority/subversion, sanctity/degradation) + overjustification effect
- **Source**: Annotated via automated methods + human validation
- **Use case**: Captures moral framing — slur-like language often activates care/harm + fairness + sanctity simultaneously. Good for training models to predict moral response from axis projections.

## Behavior-in-the-wild Persuasiveness (Anthropic/Stanford)
- **Design**: A/B tested text variants → measured actual human persuasion outcomes
- **Relevance**: Gold standard for "same message, different wording" comparison — exactly what embedding axis deltas capture
- **Note**: May require application/access — verify availability

## Key Pipeline Pattern
1. Embed all texts from dataset (GoEmotions/Moral Foundations)
2. Project onto your discovered semantic axes
3. Train a lightweight model (logistic regression, small MLP) to predict: given axis scores → which emotion labels / moral frames will readers experience?
4. Validate on held-out texts — check if axis profile + prediction matches actual label distribution

## Limitations of Existing Datasets
- Most provide **flat labels** (emotion category), not continuous reaction intensity
- Reddit-specific population bias (demographics, culture)
- No dataset captures "slur-trigger" as a continuous variable — most use categorical labels
- Political/social framing datasets are sparse; most emotion data is from social media comments, not controlled messaging studies
