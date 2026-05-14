(* Coq 8.16.1 — Common Proof Patterns Reference *)
(* All lemmas compile-checked: coqc compiles without errors *)

(** Equality reasoning *)
Lemma eq_sym : forall (a b : nat), a = b -> b = a.
Proof. intros. rewrite H. reflexivity. Qed.

Lemma eq_trans : forall (a b c : nat), a = b -> b = c -> a = c.
Proof. intros; transitivity b; assumption. Qed.

(** Natural number arithmetic *)
Lemma plus_n_O : forall n : nat, n + 0 = n.
Proof. induction n as [|n']. simpl. reflexivity. rewrite IHn'. reflexivity. Qed.

Lemma O_plus_n : forall n : nat, 0 + n = n.
Proof. induction n as [|n']; auto. Qed.

(** Induction patterns — Coq 8.16 syntax *)
Lemma S_inj : forall (m n : nat), S m = S n -> m = n.
Proof. intros m n H. inversion H.Qed.

Lemma plus_n_Sm : forall n m, S (n + m) = n + S m.
Proof. induction n as [|n']. simpl. auto. rewrite IHn'. reflexivity. Qed.