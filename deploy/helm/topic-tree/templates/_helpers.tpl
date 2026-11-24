{{- define "topic-tree.name" -}}topic-tree{{- end -}}

{{- define "topic-tree.fullname" -}}
{{- if contains "topic-tree" .Release.Name -}}{{ .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else -}}{{ printf "%s-topic-tree" .Release.Name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- end -}}

{{- define "topic-tree.labels" -}}
app.kubernetes.io/name: {{ include "topic-tree.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "topic-tree.selectorLabels" -}}
app.kubernetes.io/name: {{ include "topic-tree.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
