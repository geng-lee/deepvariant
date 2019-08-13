# Copyright 2019 Google LLC.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Tests for deepvariant .vcf_caller."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import sys
if 'google' in sys.modules and 'google.protobuf' not in sys.modules:
  del sys.modules['google']




from absl.testing import absltest
from absl.testing import parameterized
import mock

from third_party.nucleus.testing import test_utils
from deepvariant import testdata
from deepvariant import vcf_caller
from deepvariant.protos import deepvariant_pb2


def setUpModule():
  testdata.init()


def _reference_model_options(p_error, max_gq, gq_resolution=1):
  return deepvariant_pb2.VariantCallerOptions(
      sample_name='UNKNOWN',
      p_error=p_error,
      max_gq=max_gq,
      gq_resolution=gq_resolution,
      ploidy=2)


class VcfCallerTests(parameterized.TestCase):

  def make_test_caller(self, p_error, max_gq, gq_resolution=1):
    options = _reference_model_options(p_error, max_gq, gq_resolution)
    return vcf_caller.VcfCaller(
        options, testdata.TRUTH_VARIANTS_VCF, use_cache_table=False)

  def fake_allele_counter(self, start_pos, counts):
    allele_counter = mock.Mock()
    # pylint: disable=g-complex-comprehension
    allele_counter.summary_counts.return_value = [
        deepvariant_pb2.AlleleCountSummary(
            ref_supporting_read_count=n_ref,
            total_read_count=n_ref + n_alt,
            ref_base=ref,
            reference_name='chr1',
            position=start_pos + i)
        for i, (n_alt, n_ref, ref) in enumerate(counts)
    ]
    # pylint: enable=g-complex-comprehension
    return allele_counter

  def test_calls_from_vcf(self):
    # Our test AlleleCounts are 5 positions:
    #
    # 10: A ref [no reads]
    # 11: G/C variant
    # 12: G ref [no reads]
    # 13: G ref [no reads]
    # 14: T/C variant
    #
    # The ref sites have no reads for ref or any alt simply because it
    # simplifies comparing them with the expected variant genotype likelihoods.
    # We aren't testing the correctness of the gvcf calculation here (that's
    # elsewhere) but rather focusing here on the separation of variants from
    # gvcf records, and the automatic merging of the gvcf blocks.
    allele_counter = self.fake_allele_counter(10, [
        (0, 0, 'A'),
        (10, 10, 'G'),
        (0, 0, 'G'),
        (0, 0, 'G'),
        (10, 10, 'T'),
    ])
    fake_candidates = [
        deepvariant_pb2.DeepVariantCall(
            variant=test_utils.make_variant(alleles=['G', 'C'], start=11)),
        deepvariant_pb2.DeepVariantCall(
            variant=test_utils.make_variant(alleles=['T', 'C'], start=14)),
    ]

    caller = self.make_test_caller(0.01, 100)
    with mock.patch.object(caller, 'cpp_variant_caller') as mock_cpp:
      mock_cpp.calls_from_vcf.return_value = fake_candidates
      candidates, _ = caller.calls_and_gvcfs(allele_counter, False)

    mock_cpp.calls_from_vcf.assert_called_once_with(allele_counter,
                                                    caller.vcf_reader)
    self.assertEqual(candidates, fake_candidates)


if __name__ == '__main__':
  absltest.main()