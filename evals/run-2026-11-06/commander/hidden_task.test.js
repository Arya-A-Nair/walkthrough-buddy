import * as commander from '../index.js';
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

function makeProgram() {
  return new commander.Command().exitOverride().configureOutput({
    writeOut: () => {},
    writeErr: () => {},
  });
}

function captureError(fn) {
  try {
    fn();
  } catch (err) {
    return err;
  }
  assert.fail('expected parse to throw');
}

describe('choices suggestion after error', () => {
  test('when option-argument is a near miss then suggest the choice', () => {
    const program = makeProgram().addOption(
      new commander.Option('--colour <shade>').choices(['red', 'blue']),
    );
    const err = captureError(() =>
      program.parse(['--colour', 'rde'], { from: 'user' }),
    );
    assert.equal(err.code, 'commander.invalidArgument');
    assert.equal(err.exitCode, 1);
    assert.equal(
      err.message,
      "error: option '--colour <shade>' argument 'rde' is invalid. Allowed choices are red, blue.\n(Did you mean red?)",
    );
  });

  test('when command-argument is a near miss then suggest the choice', () => {
    const program = makeProgram()
      .addArgument(
        new commander.Argument('<size>').choices(['small', 'medium', 'large']),
      )
      .action(() => {});
    const err = captureError(() =>
      program.parse(['meduim'], { from: 'user' }),
    );
    assert.equal(err.code, 'commander.invalidArgument');
    assert.equal(
      err.message,
      "error: command-argument value 'meduim' is invalid for argument 'size'. Allowed choices are small, medium, large.\n(Did you mean medium?)",
    );
  });

  test('when several choices equally close then suggest all of them', () => {
    const program = makeProgram().addOption(
      new commander.Option('--mode <m>').choices(['cat', 'car', 'dog']),
    );
    const err = captureError(() =>
      program.parse(['--mode', 'cax'], { from: 'user' }),
    );
    assert.ok(
      err.message.endsWith('\n(Did you mean one of car, cat?)'),
      err.message,
    );
  });

  test('when value from env is a near miss then suggest the choice', (t) => {
    process.env.HIDDEN_TASK_COLOUR = 'bleu';
    t.after(() => delete process.env.HIDDEN_TASK_COLOUR);
    const program = makeProgram().addOption(
      new commander.Option('--colour <shade>')
        .choices(['red', 'blue'])
        .env('HIDDEN_TASK_COLOUR'),
    );
    const err = captureError(() => program.parse([], { from: 'user' }));
    assert.equal(
      err.message,
      "error: option '--colour <shade>' value 'bleu' from env 'HIDDEN_TASK_COLOUR' is invalid. Allowed choices are red, blue.\n(Did you mean blue?)",
    );
  });

  test('when nothing is close then message is unchanged', () => {
    const program = makeProgram().addOption(
      new commander.Option('--colour <shade>').choices(['red', 'blue']),
    );
    const err = captureError(() =>
      program.parse(['--colour', 'green'], { from: 'user' }),
    );
    assert.equal(
      err.message,
      "error: option '--colour <shade>' argument 'green' is invalid. Allowed choices are red, blue.",
    );
  });

  test('when showSuggestionAfterError(false) then no suggestion', () => {
    const program = makeProgram()
      .showSuggestionAfterError(false)
      .addOption(
        new commander.Option('--colour <shade>').choices(['red', 'blue']),
      );
    const err = captureError(() =>
      program.parse(['--colour', 'rde'], { from: 'user' }),
    );
    assert.equal(
      err.message,
      "error: option '--colour <shade>' argument 'rde' is invalid. Allowed choices are red, blue.",
    );
  });

  test('when showSuggestionAfterError(false) on program then subcommand gives no suggestion', () => {
    const program = makeProgram().showSuggestionAfterError(false);
    program
      .command('paint')
      .addArgument(new commander.Argument('<shade>').choices(['red', 'blue']))
      .action(() => {});
    const err = captureError(() =>
      program.parse(['paint', 'rde'], { from: 'user' }),
    );
    assert.equal(
      err.message,
      "error: command-argument value 'rde' is invalid for argument 'shade'. Allowed choices are red, blue.",
    );
  });

  test('when custom parser without choices throws then no suggestion added', () => {
    const program = makeProgram().option('--colour <shade>', 'shade', () => {
      throw new commander.InvalidArgumentError('Try red.');
    });
    const err = captureError(() =>
      program.parse(['--colour', 'rde'], { from: 'user' }),
    );
    assert.equal(
      err.message,
      "error: option '--colour <shade>' argument 'rde' is invalid. Try red.",
    );
  });
});
