## scores
The model gives each of the {n_tokens} tokens a score.

## exp
Make each score positive with $e^{z}$.

## sum
Add them all: $\sum_j e^{z_j}$.

## divide
Divide each by the sum: $p_i = e^{z_i} / \sum_j e^{z_j}$.

## probs
Now they are probabilities. The top one is {p_top:.4f}.

## top
The highest score wins the most probability; see [[softmax#scores]].
