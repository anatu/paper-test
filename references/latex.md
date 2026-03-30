# LaTeX Reference

## Document Class Selection

Choose based on the target venue:

| Venue | Document class | Notes |
|-------|---------------|-------|
| NeurIPS | `\documentclass{article}` + neurips style | Use `neurips_2024.sty` (or current year) |
| ICML | `\documentclass{article}` + icml style | Use `icml2024.sty` (or current year) |
| ACL/EMNLP | `\documentclass[11pt,a4paper]{article}` + acl style | Use `acl.sty` |
| AAAI | `\documentclass[letterpaper]{article}` + aaai style | Use `aaai24.sty` |
| ACM (SIGCHI, FAccT) | `\documentclass[sigconf]{acmart}` | ACM's unified class |
| JMLR | `\documentclass[twoside]{article}` + jmlr style | Use `jmlr.sty` |
| Generic / draft | `\documentclass[11pt,a4paper]{article}` | Good for early drafts |

When the venue is unspecified, use the generic article class with reasonable defaults.

## Standard Preamble

```latex
\documentclass[11pt,a4paper]{article}

% --- Encoding & fonts ---
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}

% --- Math ---
\usepackage{amsmath,amssymb,amsthm}
\usepackage{mathtools}          % extends amsmath

% --- Tables ---
\usepackage{booktabs}           % \toprule, \midrule, \bottomrule
\usepackage{multirow}
\usepackage{array}

% --- Figures ---
\usepackage{graphicx}
\usepackage{subcaption}         % subfigures
\usepackage[dvipsnames]{xcolor} % named colors

% --- Layout ---
\usepackage[margin=1in]{geometry}
\usepackage{setspace}           % \onehalfspacing if needed

% --- References ---
\usepackage[colorlinks=true,citecolor=blue,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage[capitalise,noabbrev]{cleveref}  % \cref, \Cref
\usepackage{natbib}
\bibliographystyle{plainnat}    % or abbrvnat, unsrtnat

% --- Algorithms ---
\usepackage{algorithm}
\usepackage{algorithmic}        % or algpseudocode

% --- Misc ---
\usepackage{enumitem}           % customize lists
\usepackage{microtype}          % better typography
\usepackage{balance}            % balance final page columns (two-column)
```

## Useful Macros

```latex
% --- Shorthand ---
\newcommand{\ie}{i.e.,\xspace}
\newcommand{\eg}{e.g.,\xspace}
\newcommand{\cf}{cf.\xspace}
\newcommand{\etal}{et al.\xspace}

% --- Math operators ---
\DeclareMathOperator*{\argmax}{arg\,max}
\DeclareMathOperator*{\argmin}{arg\,min}
\DeclareMathOperator{\E}{\mathbb{E}}
\newcommand{\R}{\mathbb{R}}
\newcommand{\N}{\mathbb{N}}

% --- Vectors and matrices ---
\renewcommand{\vec}[1]{\mathbf{#1}}
\newcommand{\mat}[1]{\mathbf{#1}}

% --- Model/method names ---
\newcommand{\methodname}{\textsc{MethodName}\xspace}  % replace as needed

% --- Notation ---
\newcommand{\dataset}{\mathcal{D}}
\newcommand{\loss}{\mathcal{L}}
\newcommand{\params}{\theta}

% --- Review helpers (remove before submission) ---
\newcommand{\todo}[1]{\textcolor{red}{\textbf{TODO:} #1}}
\newcommand{\note}[1]{\textcolor{blue}{\textbf{Note:} #1}}
```

## Document Structure Template

```latex
\begin{document}

\title{Your Paper Title: Subtitle if Needed}
\author{
  Author One\thanks{Equal contribution.} \\
  Affiliation One \\
  \texttt{author1@example.com}
  \and
  Author Two\footnotemark[1] \\
  Affiliation Two \\
  \texttt{author2@example.com}
}
\date{}

\maketitle

\begin{abstract}
  Your abstract here. 150--250 words. No citations.
\end{abstract}

% --- Optional: keywords ---
% \keywords{keyword1, keyword2, keyword3}

\section{Introduction}
\label{sec:intro}

\section{Background and Definitions}
\label{sec:background}

\section{Taxonomy}
\label{sec:taxonomy}

\section{Survey of Methods}
\label{sec:survey}
\subsection{Category A}
\label{sec:category-a}
\subsection{Category B}
\label{sec:category-b}
\subsection{Category C}
\label{sec:category-c}

\section{Comparative Analysis}
\label{sec:comparison}

\section{Discussion}
\label{sec:discussion}

\section{Conclusion}
\label{sec:conclusion}

\bibliography{references}

\appendix
\section{Supplementary Material}
\label{sec:appendix}

\end{document}
```

## Compilation

### Standard workflow
```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or with `latexmk` (recommended):
```bash
latexmk -pdf main.tex
```

### Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Undefined control sequence` | Missing package or typo in command | Check `\usepackage` declarations |
| `Citation undefined` | BibTeX not run or key mismatch | Run `bibtex`, check `.bib` keys |
| `Float too large` | Figure/table exceeds column/page width | Resize with `\resizebox` or `width=\columnwidth` |
| `Overfull hbox` | Text exceeds margins | Rephrase, add `\allowbreak`, or use `\sloppy` locally |
| `Missing $ inserted` | Math symbol outside math mode | Wrap in `$...$` |

## Best Practices

1. **One sentence per line** in the `.tex` source — makes diffs and version control cleaner
2. **Label everything**: `\label{sec:...}`, `\label{fig:...}`, `\label{tab:...}`, `\label{eq:...}`
3. **Use `\cref`** instead of manual "Figure 1" — it auto-generates the correct prefix
4. **Keep the `.bib` file separate** — one file, alphabetized, shared across projects if possible
5. **Use `\input{sections/intro}` to split large papers** — one file per section
6. **Never hardcode cross-references** — always use `\ref` or `\cref`
7. **Use `~` (non-breaking space)** before `\cite`, `\ref`, `\cref` to prevent line breaks:
   `as shown in~\cref{fig:taxonomy}`
8. **Compile frequently** — catch errors early, especially after adding new packages
