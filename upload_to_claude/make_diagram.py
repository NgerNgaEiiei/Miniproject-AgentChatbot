"""CS Advisor Agent - System Architecture Diagram"""
from graphviz import Digraph

g = Digraph("cs_advisor", format="png", engine="dot")
g.attr(rankdir="LR", bgcolor="white", splines="spline",
       nodesep="0.55", ranksep="1.1", pad="0.3",
       fontname="Arial", compound="true")
g.attr("node", fontname="Arial", fontsize="11", margin="0.18,0.10")
g.attr("edge", fontname="Arial", fontsize="9", color="#444444")

# --- Online flow nodes ---
g.node("user", "User",
       shape="circle", style="filled",
       fillcolor="#E3F2FD", color="#1976D2",
       width="0.75", fixedsize="true")

g.node("agent",
       '<<B>Agent</B><BR/><FONT POINT-SIZE="9">decide_action() + LLM</FONT>>',
       shape="box", style="rounded,filled",
       fillcolor="#FFF3E0", color="#E65100",
       width="2.0", height="0.9")

tool_label = (
    '<<B>Tools</B><BR ALIGN="CENTER"/>'
    '<FONT POINT-SIZE="9">'
    'count_courses<BR ALIGN="LEFT"/>'
    'get_course_detail<BR ALIGN="LEFT"/>'
    'check_prerequisite<BR ALIGN="LEFT"/>'
    'get_learning_path<BR ALIGN="LEFT"/>'
    'get_study_plan<BR ALIGN="LEFT"/>'
    '</FONT>>'
)
g.node("tool", tool_label,
       shape="box", style="rounded,filled",
       fillcolor="#F3E5F5", color="#6A1B9A",
       width="2.0", height="1.6")

g.node("sqlite", "SQLite",
       shape="cylinder", style="filled",
       fillcolor="#E8F5E9", color="#2E7D32",
       width="1.0", height="1.0", fixedsize="true")

g.node("gen_resp",
       '<<B>generate_response()</B><BR/><FONT POINT-SIZE="9">+ LLM</FONT>>',
       shape="box", style="rounded,filled",
       fillcolor="#FFF3E0", color="#E65100",
       width="2.1", height="0.9")

# --- RAG cluster ---
with g.subgraph(name="cluster_rag") as c:
    c.attr(label="RAG  (skipped for count_courses / get_study_plan)",
           style="rounded,dashed", color="#00695C",
           fontcolor="#00695C", fontsize="10",
           labeljust="l", margin="16")
    c.node("query_emb",
           '<<B>Query Embedding</B><BR/><FONT POINT-SIZE="9">sentence-transformers</FONT>>',
           shape="box", style="rounded,filled",
           fillcolor="#FFF8E1", color="#F57F17",
           width="2.0", height="0.9")
    c.node("qdrant", "Qdrant",
           shape="cylinder", style="filled",
           fillcolor="#E0F2F1", color="#00695C",
           width="1.0", height="1.0", fixedsize="true")

# --- Offline ETL cluster ---
with g.subgraph(name="cluster_etl") as c:
    c.attr(label="Offline: ETL Pipeline",
           style="rounded,dashed", color="#AD1457",
           fontcolor="#AD1457", fontsize="10",
           labeljust="l", margin="16")
    c.node("pdf",
           '<<B>TQF-2</B><BR/><FONT POINT-SIZE="9">CS Curriculum<BR/>(B.E. 2566)</FONT>>',
           shape="note", style="filled",
           fillcolor="#FFFDE7", color="#9E9D24",
           width="1.5", height="1.0")
    c.node("etl", "ETL\nPipeline",
           shape="box", style="rounded,filled",
           fillcolor="#FCE4EC", color="#AD1457",
           width="1.3", height="0.9")
    c.node("doc_emb",
           '<<B>Document Embedding</B><BR/><FONT POINT-SIZE="9">sentence-transformers</FONT>>',
           shape="box", style="rounded,filled",
           fillcolor="#FFF8E1", color="#F57F17",
           width="2.0", height="0.9")

# --- Online edges (use dir=both + tail/head labels to avoid overlap) ---
g.edge("user", "agent",
       taillabel=" 1. Ask ", headlabel=" 11. Response ",
       dir="both", labeldistance="2.2", labelangle="25")
g.edge("agent", "tool",
       taillabel=" 2. Call tool ", headlabel=" 5. tool_result ",
       dir="both", labeldistance="2.2", labelangle="25")
g.edge("tool", "sqlite",
       taillabel=" 3. Query ", headlabel=" 4. Rows ",
       dir="both", labeldistance="2.2", labelangle="25")

g.edge("agent", "query_emb", label=" 6. Embed query ",
       color="#00695C", fontcolor="#00695C", style="dashed")
g.edge("query_emb", "qdrant", label=" 7. Semantic search ",
       color="#00695C", fontcolor="#00695C")
g.edge("qdrant", "agent", label=" 8. rag_docs ",
       color="#00695C", fontcolor="#00695C",
       style="dashed", constraint="false")

g.edge("agent", "gen_resp",
       taillabel=" 9. context ", headlabel=" 10. final_answer ",
       dir="both", labeldistance="2.2", labelangle="25")

# --- Offline edges ---
g.edge("pdf", "etl", label=" Extract ",
       color="#AD1457", fontcolor="#AD1457")
g.edge("etl", "sqlite", label=" Structured data ",
       color="#AD1457", fontcolor="#AD1457",
       style="bold", constraint="false")
g.edge("etl", "doc_emb", label=" Course descriptions ",
       color="#AD1457", fontcolor="#AD1457")
g.edge("doc_emb", "qdrant", label=" Vectors ",
       color="#F57F17", fontcolor="#F57F17",
       style="bold", constraint="false")

result = g.render(filename="cs_advisor_architecture",
                  directory="/sessions/admiring-kind-newton/mnt/outputs",
                  cleanup=False)
print("Saved:", result)
