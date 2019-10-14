# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Predict heterologous pathways for the given organism and chemical of interest"""

import warnings

# Silence the following warning which appears at cameo import:
#   UserWarning: Cannot import any plotting library. Please install one of
#   'plotly', 'bokeh' or 'ggplot' if you want to use any plotting function
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import cameo
